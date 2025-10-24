# 感知层设计指南

## 📖 概述

本项目采用**感知抽象层**设计，将环境感知逻辑与多智能体框架逻辑分离。这样设计的好处：

✅ **易于切换**：可以轻松在模拟环境和真实XR应用之间切换  
✅ **易于测试**：先用模拟环境验证框架逻辑，再接入真实XR  
✅ **易于扩展**：支持不同的XR平台（Unity、Unreal、WebXR等）  
✅ **解耦合**：Agent决策逻辑不依赖具体的感知实现  

## 🏗️ 架构设计

### 感知接口层次

```
┌─────────────────────────────────────┐
│   Multi-Agent Framework (nodes.py)  │
│   PerceptionNode, ExecutionNode     │
└──────────────┬──────────────────────┘
               │ 使用
               ▼
┌─────────────────────────────────────┐
│   PerceptionInterface (抽象基类)     │
│   - get_visible_objects()           │
│   - get_agent_state()               │
│   - execute_action()                │
│   - get_environment_info()          │
└──────────────┬──────────────────────┘
               │ 实现
        ┌──────┴──────┐
        ▼             ▼
┌──────────────┐  ┌──────────────┐
│MockPerception│  │ XRPerception │
│  (模拟环境)   │  │ (真实XR应用) │
└──────────────┘  └──────────────┘
```

## 🔧 核心接口

### `PerceptionInterface` 抽象基类

所有感知实现都必须实现以下方法：

```python
class PerceptionInterface(ABC):
    
    @abstractmethod
    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        """获取Agent当前位置可见的物体"""
        pass
    
    @abstractmethod
    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        """获取Agent当前状态（位置、朝向等）"""
        pass
    
    @abstractmethod
    def execute_action(self, agent_id: str, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """执行Agent动作并返回新状态"""
        pass
    
    @abstractmethod
    def get_environment_info(self) -> Dict[str, Any]:
        """获取环境全局信息"""
        pass
```

## 📦 当前实现

### 1. MockPerception（模拟感知）

**用途**：开发和测试阶段使用

**特点**：
- 使用简单字典模拟环境
- 一维线性空间，每个位置有1-3个物体
- 快速、轻量、无需外部依赖

**示例**：
```python
from utils.perception_interface import create_perception

# 创建模拟环境
env = create_environment(num_positions=10)

# 创建模拟感知
perception = create_perception("mock", env=env)

# 使用
visible = perception.get_visible_objects("Agent1", position=0)
print(f"Agent sees: {visible}")

# 执行动作
new_state = perception.execute_action("Agent1", "forward")
print(f"New position: {new_state['position']}")
```

### 2. XRPerception（真实XR感知）

**用途**：接入真实XR应用（生产环境）

**当前状态**：模板实现，需要根据实际XR平台填充

**待实现的方法**：
- 连接XR应用的API/SDK
- 获取真实场景数据
- 执行真实Agent动作

## 🚀 如何接入真实XR应用

### 步骤1：确定XR平台和API

首先确定你要测试的XR应用：
- Unity (C# API / Unity ML-Agents)
- Unreal Engine (Blueprint / C++ API)
- WebXR (JavaScript API)
- 其他自定义XR平台

### 步骤2：实现XRPerception类

在 `utils/perception_interface.py` 中，找到 `XRPerception` 类并实现：

#### 示例1：Unity平台

```python
class XRPerception(PerceptionInterface):
    def __init__(self, unity_client, config=None):
        """
        Args:
            unity_client: Unity应用的客户端（如gRPC、HTTP、WebSocket）
        """
        self.unity_client = unity_client
        self.config = config or {}
    
    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        """通过Unity API获取可见物体"""
        try:
            # 调用Unity的Raycast或场景查询API
            response = self.unity_client.GetVisibleObjects(
                agent_id=agent_id,
                raycast_distance=10.0
            )
            return [obj.name for obj in response.objects]
        except Exception as e:
            print(f"[XRPerception] Error: {e}")
            return []
    
    def execute_action(self, agent_id: str, action: str, params=None) -> Dict:
        """通过Unity API执行动作"""
        try:
            # 调用Unity的角色控制API
            if action == "forward":
                response = self.unity_client.MoveAgent(
                    agent_id=agent_id,
                    direction="forward",
                    distance=1.0
                )
            elif action == "backward":
                response = self.unity_client.MoveAgent(
                    agent_id=agent_id,
                    direction="backward",
                    distance=1.0
                )
            
            return {
                "position": response.new_position,
                "rotation": response.new_rotation,
                "visible_objects": response.visible_objects
            }
        except Exception as e:
            print(f"[XRPerception] Error: {e}")
            return {}
```

#### 示例2：WebXR平台

```python
class XRPerception(PerceptionInterface):
    def __init__(self, websocket_url, config=None):
        """
        Args:
            websocket_url: WebXR应用的WebSocket地址
        """
        import websocket
        self.ws = websocket.create_connection(websocket_url)
        self.config = config or {}
    
    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        """通过WebSocket获取可见物体"""
        message = json.dumps({
            "type": "get_visible_objects",
            "agent_id": agent_id
        })
        self.ws.send(message)
        response = json.loads(self.ws.recv())
        return response.get("objects", [])
    
    def execute_action(self, agent_id: str, action: str, params=None) -> Dict:
        """通过WebSocket执行动作"""
        message = json.dumps({
            "type": "execute_action",
            "agent_id": agent_id,
            "action": action
        })
        self.ws.send(message)
        response = json.loads(self.ws.recv())
        return response.get("new_state", {})
```

### 步骤3：在main.py中使用

修改 `main.py` 使用真实XR感知：

```python
def main(perception_type: str = "xr"):
    # ... 创建环境等 ...
    
    if perception_type == "xr":
        # 创建XR客户端
        from your_xr_sdk import UnityClient  # 替换为实际的SDK
        
        xr_client = UnityClient(
            host="localhost",
            port=8080
        )
        xr_client.connect()
        
        # 创建XR感知
        perception = create_perception("xr", xr_client=xr_client)
        print("[System] Using XRPerception (real XR application)")
    else:
        # 使用模拟感知
        perception = create_perception("mock", env=global_env)
    
    # ... 启动agents ...
```

### 步骤4：测试流程

1. **先用Mock测试**：
   ```bash
   python main.py  # 默认使用mock
   ```

2. **确认框架逻辑正确后，切换到XR**：
   ```bash
   # 修改main.py或添加命令行参数
   python main.py --perception xr
   ```

3. **调试XR连接**：
   - 确保XR应用正在运行
   - 检查网络连接（端口、防火墙）
   - 查看日志输出

## 🔍 常见问题

### Q1: 如何调试感知层？

在 `XRPerception` 的每个方法中添加日志：

```python
def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
    print(f"[XRPerception] Getting visible objects for {agent_id} at {position}")
    try:
        result = self.xr_client.get_scene(agent_id)
        print(f"[XRPerception] Received {len(result.visible_objects)} objects")
        return result.visible_objects
    except Exception as e:
        print(f"[XRPerception] ERROR: {e}")
        return []
```

### Q2: XR应用崩溃了怎么办？

添加重试逻辑和降级策略：

```python
def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
    for retry in range(3):
        try:
            return self.xr_client.get_scene(agent_id).visible_objects
        except Exception as e:
            print(f"[XRPerception] Retry {retry+1}/3: {e}")
            time.sleep(1)
    
    # 降级：返回空列表或使用缓存
    return []
```

### Q3: 如何处理XR应用的异步响应？

如果XR API是异步的，可以使用异步版本：

```python
import asyncio

class AsyncXRPerception(PerceptionInterface):
    async def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        response = await self.xr_client.get_scene_async(agent_id)
        return response.visible_objects
```

然后修改Node使用AsyncNode（参考PocketFlow的Async文档）。

### Q4: 如何支持多种XR平台？

创建多个Perception实现：

```python
class UnityPerception(PerceptionInterface):
    # Unity特定实现
    pass

class UnrealPerception(PerceptionInterface):
    # Unreal特定实现
    pass

class WebXRPerception(PerceptionInterface):
    # WebXR特定实现
    pass

# 在工厂函数中选择
def create_perception(perception_type: str, **kwargs):
    if perception_type == "unity":
        return UnityPerception(**kwargs)
    elif perception_type == "unreal":
        return UnrealPerception(**kwargs)
    elif perception_type == "webxr":
        return WebXRPerception(**kwargs)
    # ...
```

## 📚 参考资料

- **Unity ML-Agents**: https://github.com/Unity-Technologies/ml-agents
- **Unreal Engine Python API**: https://docs.unrealengine.com/en-US/PythonAPI/
- **WebXR Device API**: https://developer.mozilla.org/en-US/docs/Web/API/WebXR_Device_API
- **gRPC (推荐用于Unity/Unreal通信)**: https://grpc.io/

## 💡 最佳实践

1. **先Mock后XR**：始终先用MockPerception验证框架逻辑
2. **添加日志**：在XRPerception的每个方法中添加详细日志
3. **错误处理**：捕获所有异常，避免整个系统崩溃
4. **性能监控**：记录每次API调用的耗时
5. **单元测试**：为XRPerception编写单元测试
6. **文档化**：记录XR API的使用方法和限制

## 🎯 下一步

1. 确定你的XR平台
2. 查看XR平台的API文档
3. 实现XRPerception类的方法
4. 测试和调试
5. 集成到main.py中

如有问题，请查看 `utils/perception_interface.py` 中的代码注释和TODO标记！

