# 系统架构详解

## 📁 文件结构与作用

### 核心文件（按执行顺序）

```
main.py (入口)
    ↓ 调用
flow.py (组装Flow)
    ↓ 使用
nodes.py (定义6个节点)
    ↓ 调用
utils/ (工具函数库)
```

---

## 1️⃣ main.py - 主程序入口

**作用**：系统的启动点，负责初始化和协调多个Agent

### 核心职责：
1. **创建全局环境** - 模拟XR空间（10个位置，每个位置有1-3个物体）
2. **初始化Agent** - 为每个Agent创建独立的shared store（包含FAISS记忆索引）
3. **启动线程** - 用Python threading让两个Agent并行运行
4. **收集结果** - 等待所有Agent完成，统计探索成果

### 关键代码流程：

```python
# 1. 创建全局环境（所有Agent共享）
global_env = {
    "objects": {0: ["chair", "table"], 1: ["lamp"], ...},  # 位置→物体映射
    "agent_positions": {},                                  # Agent当前位置
    "message_queue": [],                                    # Agent间消息
    "explored_by_all": set()                                # 全局探索统计
}

# 2. 为每个Agent创建私有存储
agent_shared = {
    "agent_id": "Agent1",
    "global_env": global_env,        # 引用全局环境
    "memory_index": create_memory(), # 独立的FAISS索引
    "memory_texts": [],              # 对应的记忆文本
    "position": 0,                   # 当前位置
    "explored_objects": set(),       # 该Agent探索过的物体
    ...
}

# 3. 创建Flow并运行
flow = create_agent_flow()
flow.run(agent_shared)  # 这会执行整个决策循环
```

### 协作关系：
- **调用** `flow.py` 的 `create_agent_flow()` 创建决策循环
- **调用** `utils/environment.py` 的 `create_environment()` 创建环境
- **调用** `utils/memory.py` 的 `create_memory()` 创建FAISS索引

---

## 2️⃣ flow.py - Flow定义

**作用**：组装Agent的决策循环，定义节点执行顺序

### 核心职责：
连接6个节点，形成循环流程

### 代码逻辑：

```python
def create_agent_flow():
    # 创建6个节点实例
    perception = PerceptionNode()
    retrieve = RetrieveMemoryNode()
    communicate = CommunicationNode()
    decide = DecisionNode(max_retries=3)  # 允许重试
    execute = ExecutionNode()
    update = UpdateMemoryNode()
    
    # 定义执行顺序（使用PocketFlow的>>连接符）
    perception >> retrieve >> communicate >> decide >> execute >> update
    
    # 定义循环：update节点返回"continue"时回到perception
    update - "continue" >> perception
    update - "end"      # 返回"end"时结束
    
    return Flow(start=perception)
```

### Flow执行流程：

```
开始
  ↓
Perception (感知环境)
  ↓
RetrieveMemory (检索相关记忆)
  ↓
Communication (读取其他Agent消息)
  ↓
Decision (LLM决策动作)
  ↓
Execution (执行动作)
  ↓
UpdateMemory (存储新记忆)
  ↓
判断：step < max_steps?
  ├─ Yes → 返回"continue" → 回到Perception
  └─ No  → 返回"end" → 结束
```

### 协作关系：
- **导入** `nodes.py` 中的所有节点类
- **被** `main.py` 调用

---

## 3️⃣ nodes.py - 节点定义

**作用**：定义6个节点，每个节点负责一个特定任务

### 节点设计模式（PocketFlow标准）

每个Node都有3个方法：
```python
class MyNode(Node):
    def prep(self, shared):
        # 从shared读取数据，准备输入
        return data_for_exec
    
    def exec(self, prep_res):
        # 执行核心逻辑（调用工具函数）
        return result
    
    def post(self, shared, prep_res, exec_res):
        # 写回shared，决定下一步动作
        return "action_name"
```

### 6个节点详解：

#### 📍 PerceptionNode - 感知节点
```python
prep:  读取 agent_id, global_env, position
exec:  调用 get_visible_objects() 获取当前位置的物体
post:  写入 visible_objects 到 shared
```

#### 🧠 RetrieveMemoryNode - 记忆检索节点
```python
prep:  读取 visible_objects，构造查询"我对这些物体有什么记忆？"
exec:  1. 调用 get_embedding() 生成查询向量
       2. 调用 search_memory() 从FAISS检索top-3相关记忆
post:  写入 retrieved_memories 到 shared
```

#### 📨 CommunicationNode - 通信节点
```python
prep:  读取 global_env 的 message_queue
exec:  过滤出发给当前Agent的消息
post:  写入 other_agent_messages 到 shared
       从队列中删除已读消息
```

#### 🤔 DecisionNode - 决策节点（核心）
```python
prep:  收集所有上下文：
       - visible_objects (当前看到的)
       - retrieved_memories (历史记忆)
       - other_agent_messages (其他Agent消息)
       - explored_objects (已探索列表)

exec:  1. 构造详细的prompt（包含所有上下文）
       2. 调用 call_llm() 获取LLM决策
       3. 解析YAML格式输出
       4. 验证action字段（必须是"forward"或"backward"）

post:  写入 action, action_reason 到 shared
```

**Prompt示例**：
```yaml
你是 Agent1，当前位置3，看到["cup", "pen"]
已探索：["chair", "table", "lamp"]

历史记忆：
- 在位置2看到lamp，决定前进
- 在位置1看到table，决定前进

其他Agent消息：
- Agent2: 我在位置5发现了keyboard

决策下一步动作：forward 或 backward
```

#### ⚡ ExecutionNode - 执行节点
```python
prep:  读取 action, agent_id, global_env
exec:  调用 execute_action() 更新环境中的Agent位置
post:  1. 更新 position, step_count
       2. 调用 add_message() 发送消息告知其他Agent
       3. 更新 explored_objects
```

#### 💾 UpdateMemoryNode - 记忆更新节点
```python
prep:  构造记忆文本：
       "在位置X看到[物体]，决定[动作]，原因：[理由]"

exec:  1. 调用 get_embedding() 生成向量
       2. 调用 add_to_memory() 存入FAISS

post:  1. 追加到 action_history
       2. 判断 step_count >= max_steps
       3. 返回 "continue" 或 "end"
```

### 线程安全机制：

```python
# 全局锁保护共享资源
env_lock = threading.Lock()

# 访问global_env时加锁
with env_lock:
    visible = get_visible_objects(position, env)
```

### 协作关系：
- **导入** `utils/` 中的所有工具函数
- **被** `flow.py` 导入和连接
- **使用** `threading.Lock` 保证线程安全

---

## 4️⃣ utils/ - 工具函数库

工具函数是"无状态"的纯函数，可被任何节点调用

### utils/environment.py - 环境模拟

```python
create_environment()      # 创建虚拟环境（位置和物体）
get_visible_objects()     # 获取指定位置的物体
execute_action()          # 执行动作，更新Agent位置
add_message()             # 发送Agent间消息
get_messages_for()        # 获取发给指定Agent的消息
```

**环境数据结构**：
```python
{
    "objects": {
        0: ["chair", "table"],
        1: ["lamp", "book", "cup"],
        2: ["pen", "phone"],
        ...
    },
    "num_positions": 10,
    "agent_positions": {"Agent1": 3, "Agent2": 5},
    "message_queue": [
        {"sender": "Agent1", "recipient": "Agent2", "message": "..."}
    ],
    "explored_by_all": {"chair", "table", "lamp", ...}
}
```

### utils/embedding.py - 文本向量化

```python
get_embedding(text)           # 单个文本 → 384维向量
get_embeddings_batch(texts)   # 批量文本 → 矩阵
```

**使用模型**：`all-MiniLM-L6-v2`（轻量级，80MB）

**为什么需要Embedding？**
- FAISS需要向量来做相似度搜索
- 将文本记忆转换为数值表示
- 实现语义检索（"我在哪见过椅子？"→找到相关记忆）

### utils/memory.py - FAISS记忆管理

```python
create_memory()              # 创建FAISS索引（L2距离）
add_to_memory()              # 添加向量+文本到索引
search_memory()              # 检索最相似的top-k记忆
```

**FAISS工作原理**：
```
记忆文本 → embedding → FAISS索引
查询文本 → embedding → 搜索索引 → 返回最相似的记忆
```

### utils/call_llm.py - LLM调用

```python
call_llm(prompt)  # 发送prompt → Gemini → 返回文本
```

**选择Gemini Flash的原因**：
- 速度快（~1秒响应）
- 成本低（$0.075/百万tokens）
- 质量足够（对于简单决策）

### 协作关系：
- **被** `nodes.py` 中的各个节点调用
- 每个工具函数都可独立测试（有`if __name__ == "__main__"`块）

---

## 🔄 完整执行流程

### 启动阶段

```
1. main.py 启动
   ↓
2. create_environment() 创建环境
   ↓
3. 为每个Agent创建 shared store + FAISS索引
   ↓
4. 启动两个线程，各自运行 run_agent()
```

### Agent决策循环（单步）

```
Step 1: PerceptionNode
  - prep: 读取 position=0
  - exec: get_visible_objects(0) → ["chair", "table"]
  - post: shared["visible_objects"] = ["chair", "table"]
  
Step 2: RetrieveMemoryNode
  - prep: 构造查询 "position 0 with chair table"
  - exec: get_embedding(query) → 向量
          search_memory(向量) → [(记忆1, 距离), (记忆2, 距离)]
  - post: shared["retrieved_memories"] = [...]
  
Step 3: CommunicationNode
  - prep: 读取 global_env["message_queue"]
  - exec: 过滤出发给自己的消息
  - post: shared["other_agent_messages"] = [...]
  
Step 4: DecisionNode 【核心】
  - prep: 收集所有上下文
  - exec: call_llm(prompt) → "action: forward, reason: ..."
  - post: shared["action"] = "forward"
  
Step 5: ExecutionNode
  - prep: 读取 action="forward"
  - exec: execute_action("forward") → new_position=1
  - post: shared["position"] = 1
          add_message("我移动到位置1")
  
Step 6: UpdateMemoryNode
  - prep: 构造记忆文本
  - exec: get_embedding(text) → 向量
          add_to_memory(向量, text)
  - post: step_count++
          if step < 15: return "continue"  → 回到Step 1
          else: return "end"  → 结束
```

### 并行协作

```
时间轴：
t=0  Agent1: Perception     Agent2: Perception
t=1  Agent1: Retrieve       Agent2: Retrieve
t=2  Agent1: Communicate    Agent2: Communicate
     └─ 读取Agent2的消息    └─ 读取Agent1的消息
t=3  Agent1: Decision       Agent2: Decision
t=4  Agent1: Execution      Agent2: Execution
     └─ 更新global_env      └─ 更新global_env (加锁)
     └─ 发送消息            └─ 发送消息
```

---

## 📊 数据流图

```
┌─────────────────────────────────────────────────────────┐
│                    Global Environment                    │
│  - objects: {位置: [物体列表]}                           │
│  - agent_positions: {Agent: 位置}                        │
│  - message_queue: [消息列表]                             │
└────────────┬───────────────────────────┬─────────────────┘
             │                           │
       ┌─────▼────┐               ┌─────▼────┐
       │ Agent1   │               │ Agent2   │
       │ Thread   │               │ Thread   │
       └─────┬────┘               └─────┬────┘
             │                           │
       ┌─────▼─────────────────────┐    │
       │ Agent1 Shared Store       │    │
       │ - memory_index (FAISS)    │    │
       │ - memory_texts            │    │
       │ - position, visible_objs  │    │
       │ - action, explored_objs   │    │
       └─────┬─────────────────────┘    │
             │                           │
       ┌─────▼────┐               ┌─────▼────┐
       │   Flow   │               │   Flow   │
       └─────┬────┘               └─────┬────┘
             │                           │
       ┌─────▼────────────────────┐     │
       │ 6个Node依次执行           │     │
       │ Perception → ... → Update│     │
       └─────┬────────────────────┘     │
             │                           │
             └──────┬───────────────────┬┘
                    │                   │
              ┌─────▼────┐        ┌─────▼────┐
              │  Utils   │        │  Utils   │
              │ - LLM    │        │ - FAISS  │
              │ - Embed  │        │ - Env    │
              └──────────┘        └──────────┘
```

---

## 🔑 关键设计决策

### 1. 为什么分离 shared store？

**Agent私有**：
- `memory_index`, `memory_texts` - 避免记忆污染
- `explored_objects` - 各自统计

**全局共享**：
- `environment` - 所有Agent在同一空间
- `message_queue` - Agent间通信

### 2. 为什么用线程而不是进程？

- Agent需要共享 `global_env`（引用传递）
- 进程需要序列化（FAISS索引难序列化）
- 线程更轻量，适合I/O密集型任务

### 3. 为什么Node不直接访问global_env？

**遵循PocketFlow最佳实践**：
- `prep()` 从shared读取
- `exec()` 纯计算，不访问shared
- `post()` 写回shared

这样：
- ✅ 职责清晰
- ✅ 易于测试
- ✅ exec()可以重试（幂等）

---

## 📝 总结：协作关系图

```
main.py (启动器)
  │
  ├─→ 创建 global_env (environment.py)
  ├─→ 创建 FAISS索引 (memory.py)
  ├─→ 调用 create_agent_flow() (flow.py)
  │     │
  │     └─→ 连接 6个Node (nodes.py)
  │           │
  │           ├─→ PerceptionNode
  │           │     └─→ get_visible_objects() (environment.py)
  │           │
  │           ├─→ RetrieveMemoryNode
  │           │     ├─→ get_embedding() (embedding.py)
  │           │     └─→ search_memory() (memory.py)
  │           │
  │           ├─→ CommunicationNode
  │           │     └─→ get_messages_for() (environment.py)
  │           │
  │           ├─→ DecisionNode
  │           │     └─→ call_llm() (call_llm.py)
  │           │
  │           ├─→ ExecutionNode
  │           │     ├─→ execute_action() (environment.py)
  │           │     └─→ add_message() (environment.py)
  │           │
  │           └─→ UpdateMemoryNode
  │                 ├─→ get_embedding() (embedding.py)
  │                 └─→ add_to_memory() (memory.py)
  │
  └─→ 启动 2个线程，各自运行 Flow
```

---

## 🎯 如何修改和扩展？

### 添加新动作（例如：左转、右转）

1. **修改 environment.py**：
   ```python
   def execute_action(agent_id, action, env):
       if action == "turn_left":
           # 实现左转逻辑
       elif action == "turn_right":
           # 实现右转逻辑
   ```

2. **修改 DecisionNode prompt**：
   ```python
   """
   可用动作：
   - forward: 前进
   - backward: 后退
   - turn_left: 左转
   - turn_right: 右转
   """
   ```

### 添加第三个Agent

在 `main.py` 中：
```python
agent3_thread = threading.Thread(
    target=run_agent,
    args=("Agent3", global_env, 15)
)
agent3_thread.start()
agent3_thread.join()
```

### 改用不同的LLM

修改 `utils/call_llm.py`：
```python
from openai import OpenAI

def call_llm(prompt):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
```

---

**希望这份详细的架构文档能帮助你理解系统的每个部分！** 🎉

