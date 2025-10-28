# Multi-Agent XR Environment Exploration

一个基于PocketFlow的多智能体协作环境探索系统，展示了两个Agent在XR虚拟环境中自主探索并通过RAG记忆系统避免重复探索。

## 系统特点

- **多Agent协作**：两个独立的Agent并行探索同一环境
- **RAG记忆系统**：使用FAISS向量数据库存储和检索探索历史
- **Agent间通信**：通过消息队列共享发现的信息
- **自主决策**：基于LLM的智能决策，综合考虑当前状态、历史记忆和其他Agent信息
- **感知抽象层**：⭐ **核心架构设计** - 支持模拟环境和真实XR应用的无缝切换
- **简单动作空间**：前进/后退两个基础动作

## 项目结构

```
test_multiuser/
├── docs/
│   └── design.md              # 详细设计文档
├── utils/
│   ├── __init__.py
│   ├── call_llm.py            # LLM调用（Gemini Flash）
│   ├── embedding.py           # 文本embedding（sentence-transformers）
│   ├── memory.py              # FAISS记忆管理
│   ├── environment.py         # 环境模拟和消息通信
│   └── perception_interface.py # ⭐ 感知抽象层（核心）
├── nodes.py                   # Agent节点定义
├── flow.py                    # Flow定义
├── main.py                    # 主程序
├── requirements.txt           # 依赖
├── README.md                  # 项目说明
└── PERCEPTION_GUIDE.md        # ⭐ 感知层设计指南
```

## 安装

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 设置环境变量：

```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your-api-key-here"

# Linux/Mac
export GEMINI_API_KEY="your-api-key-here"
```

## 运行（单 Agent 简化）

- 启动集中环境服务（一次即可）
```bash
uvicorn env_server:app --host 0.0.0.0 --port 8000
```

- 在每台机器各自启动一个 Agent：
```bash
# 远程消息/环境（remote）。如需仅聊天：设置 MESSAGING_ONLY=1
ENV_SERVER_URL=http://<server_ip>:8000 python main.py --perception remote --agent-id Laptop

# Unity 控制（pyautogui），需保证 Unity 窗口已聚焦
ENV_SERVER_URL=http://<server_ip>:8000 python main.py --perception unity --agent-id Lab \
  --screenshot_dir "$SCREENSHOT_DIR"  # 可选，使用环境变量见 main.py 注释
```

注意：`main.py` 现在默认只启动一个 agent（通过 `--agent-id` 指定）。

## 分布式（Remote）模式：多机运行 Agents

现在支持通过一个中心化环境服务让不同机器上的 Agents 共享同一环境与消息。

### 1) 启动环境服务（任意一台机器）

```bash
pip install fastapi uvicorn pydantic
python env_server.py  # 默认 0.0.0.0:8000
```

### 2) 在不同机器上启动 Agents

每台 Agent 机器设置服务地址并以 remote 模式运行：

```bash
export ENV_SERVER_URL="http://<server_host>:8000"
python -c "import main; main.main('remote')"
```

说明：
- 多台机器上的 Agents 共享集中化的世界状态（位置、全局探索集合、消息队列）。
- 消息与动作更新通过环境服务完成，Agent 本地的记忆索引仍然是各自独立的。

## 系统架构

### Agent决策循环

每个Agent包含6个节点的循环流程：

```
Perception (感知) → RetrieveMemory (检索记忆) → Communication (通信) 
    ↑                                                      ↓
    |                                                 Decision (决策)
    |                                                      ↓
UpdateMemory (更新记忆) ← Execution (执行) ←─────────────┘
    |
    └─→ continue (继续循环) / end (结束)
```

### 节点说明

1. **PerceptionNode**: 感知当前位置的物体
2. **RetrieveMemoryNode**: 从FAISS检索相关历史记忆
3. **CommunicationNode**: 读取其他Agent的消息
4. **DecisionNode**: 基于所有上下文使用LLM决策动作
5. **ExecutionNode**: 执行动作并更新环境
6. **UpdateMemoryNode**: 将新记忆存入FAISS

### 数据设计

**全局环境（共享）**:
- 环境布局（每个位置的物体）
- Agent位置
- 消息队列
- 全局探索统计

**Agent私有存储**:
- Agent ID和当前位置
- FAISS记忆索引
- 当前观察和决策
- 探索历史

## 设计特点

### 1. 感知抽象层 ⭐ **核心架构**

**问题**：如何让同一套框架既能用于开发测试，又能接入真实XR应用？

**解决方案**：定义 `PerceptionInterface` 抽象接口，支持多种实现：

```python
# 开发阶段：使用模拟环境
perception = create_perception("mock", env=mock_env)

# 生产阶段：接入真实XR应用
perception = create_perception("xr", xr_client=unity_client)
```

**优势**：
- 框架代码（nodes.py, flow.py）无需修改
- 开发时用Mock验证逻辑，上线时切换到真实XR
- 支持多种XR平台（Unity、Unreal、WebXR等）

详见：[PERCEPTION_GUIDE.md](./PERCEPTION_GUIDE.md)

### 2. 简单而有效的RAG

使用轻量级模型（all-MiniLM-L6-v2）和FAISS实现快速记忆检索：
- 每次决策前检索相关历史
- 避免重复探索已知区域
- 存储成本低，检索速度快

### 3. Agent间异步通信

通过消息队列实现：
- Agent可以分享发现
- 避免冲突和重复工作
- 松耦合设计，易于扩展

### 4. 线程安全

使用锁保护共享资源：
- 消息队列读写
- 全局探索记录
- 感知实现内部的线程安全

### 5. LLM驱动的智能决策

每个决策综合考虑：
- 当前观察（可见物体）
- 历史记忆（之前探索过的区域）
- 其他Agent消息（避免重复）
- 探索目标（最大化新物体）

## 扩展方向

### 当前待完成

1. **接入真实XR应用** ⭐ **最重要**
   - 确定目标XR平台（Unity/Unreal/WebXR等）
   - 实现 `XRPerception` 类
   - 测试真实环境下的Agent行为
   - 参考：[PERCEPTION_GUIDE.md](./PERCEPTION_GUIDE.md)

### 未来增强

2. **更多动作**：左转、右转、跳跃、交互等
3. **更复杂环境**：2D/3D空间、动态物体、障碍物
4. **更多Agent**：支持>2个Agent协作
5. **任务导向**：寻找特定物体、完成特定任务
6. **可视化**：实时显示Agent位置和探索进度
7. **持久化**：保存探索历史到数据库

## 技术栈

- **Framework**: PocketFlow（100行的轻量级LLM框架）
- **LLM**: Google Gemini 2.0 Flash（快速且便宜）
- **Embedding**: sentence-transformers (all-MiniLM-L6-v2)
- **Vector DB**: FAISS (Facebook AI Similarity Search)
- **Concurrency**: Python threading

## 参考文档

详细设计说明见 `docs/design.md`

## License

MIT

