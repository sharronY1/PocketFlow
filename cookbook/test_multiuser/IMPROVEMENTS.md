# 系统改进说明

## 📅 改进日期
2025年

## 🎯 改进目标
解决消息系统的两个核心问题：
1. 消息"一次性消费"导致历史消息无法回顾
2. 其他Agent的消息不会存入接收方的记忆系统

---

## ✅ 已完成的改进

### 1. 添加消息历史记录功能

**文件**: `utils/environment.py`

#### 改动1：在环境中添加 `message_history`

```python
# 改动前
return {
    "objects": objects,
    "message_queue": [],
    "explored_by_all": set()
}

# 改动后
return {
    "objects": objects,
    "message_queue": [],
    "message_history": [],  # ← 新增：保留所有历史消息
    "explored_by_all": set()
}
```

#### 改动2：发送消息时同时保存到历史

```python
# 改动前
def add_message(env, sender, recipient, message):
    env["message_queue"].append({
        "sender": sender,
        "recipient": recipient,
        "message": message
    })

# 改动后
def add_message(env, sender, recipient, message):
    msg = {
        "sender": sender,
        "recipient": recipient,
        "message": message
    }
    env["message_queue"].append(msg)
    
    # 同时保存到历史记录（永不删除）
    if "message_history" not in env:
        env["message_history"] = []
    env["message_history"].append(msg.copy())
```

**效果**：
- ✅ 消息队列继续正常工作（一次性消费）
- ✅ 所有历史消息被永久保存在 `message_history` 中
- ✅ 可以在任何时候查看完整的消息历史

---

### 2. 将消息存入Agent记忆系统

**文件**: `nodes.py`

#### 改动：UpdateMemoryNode 的 prep 方法

```python
# 改动前
def prep(self, shared):
    memory_text = (
        f"At position {shared['position']}, "
        f"I saw {shared['visible_objects']}. "
        f"I decided to {shared['action']}. "
        f"Reason: {shared['action_reason']}"
    )
    return memory_text, shared["memory_index"], shared["memory_texts"]

# 改动后
def prep(self, shared):
    # 构造基础记忆文本（自己的经验）
    memory_text = (
        f"At position {shared['position']}, "
        f"I saw {shared['visible_objects']}. "
        f"I decided to {shared['action']}. "
        f"Reason: {shared['action_reason']}"
    )
    
    # 添加其他Agent的消息（如果有）
    if shared.get("other_agent_messages"):
        messages_parts = []
        for msg in shared["other_agent_messages"]:
            messages_parts.append(f"{msg['sender']}: {msg['message']}")
        
        messages_summary = "; ".join(messages_parts)
        memory_text += f" | Context from others: {messages_summary}"
    
    return memory_text, shared["memory_index"], shared["memory_texts"]
```

**效果**：
- ✅ Agent的记忆同时包含自己的经验和收到的消息
- ✅ 可以通过FAISS语义搜索回忆其他Agent的消息
- ✅ 信息不会丢失

**记忆示例**：

改动前：
```
"At position 2, I saw ['cup']. I decided to backward. Reason: 避开已探索区域"
```

改动后：
```
"At position 2, I saw ['cup']. I decided to backward. Reason: 避开已探索区域 | Context from others: Agent1: 我在位置3发现了keyboard、mouse、monitor"
```

---

### 3. 增强DecisionNode的Prompt

**文件**: `nodes.py`

#### 改动：强调消息的重要性

```python
# 改动前
Messages from other agents:
{messages_text}

Task goal: Explore as many new objects as possible...

# 改动后
**Messages from other agents (IMPORTANT - consider these in your decision):**
{messages_text}

Task goal: Explore as many new objects as possible...

Decision strategy:
- If other agents reported finding new objects at nearby positions, consider moving there
- If other agents already explored certain areas, avoid those to prevent duplication
- Share important discoveries with other agents
```

#### 改动：更新YAML输出格式说明

```python
# 改动前
thinking: Your thought process (consider whether to explore new areas or areas already explored)
reason: Reason for choosing this action

# 改动后
thinking: Your thought process (MUST consider messages from other agents if any, and whether to explore new areas)
reason: Reason for choosing this action (mention other agents' messages if they influenced your decision)
```

**效果**：
- ✅ LLM更倾向于考虑其他Agent的消息
- ✅ 决策理由中更可能提到消息内容
- ✅ 协作更加明确

---

### 4. 添加调试输出

**文件**: `main.py`

#### 改动1：Agent总结中显示记忆样本

```python
# 显示前3条记忆
if agent_shared['memory_texts']:
    print(f"\nSample memories:")
    for i, mem in enumerate(agent_shared['memory_texts'][:3], 1):
        print(f"  {i}. {mem[:120]}...")
```

#### 改动2：系统总结中显示消息历史

```python
# 显示前10条消息
if "message_history" in global_env and global_env["message_history"]:
    print(f"\nMessage history ({len(global_env['message_history'])} messages):")
    for i, msg in enumerate(global_env["message_history"][:10], 1):
        print(f"  {i}. {msg['sender']} → {msg['recipient']}: {msg['message'][:80]}")
```

**效果**：
- ✅ 可以验证消息是否被正确存入记忆
- ✅ 可以查看完整的消息历史
- ✅ 方便调试和分析Agent行为

---

## 📊 改进前后对比

### 消息生命周期

#### 改动前
```
t=0: Agent1 发送消息
     └─→ message_queue = [msg]

t=1: Agent2 读取消息
     └─→ message_queue = []  ← 消息被删除

t=2: Agent2 第二次决策
     └─→ 无法访问之前的消息 ❌
```

#### 改动后
```
t=0: Agent1 发送消息
     └─→ message_queue = [msg]
     └─→ message_history = [msg]  ← 永久保存

t=1: Agent2 读取消息
     └─→ message_queue = []
     └─→ message_history = [msg]  ← 仍然存在
     └─→ 消息存入 Agent2 的 FAISS 记忆 ← 可搜索

t=2: Agent2 第二次决策
     └─→ 可以通过 message_history 查看 ✅
     └─→ 可以通过 FAISS 搜索回忆 ✅
```

### 记忆内容对比

#### Agent2 收到 Agent1 的消息："位置3有keyboard和mouse"

**改动前**：
```
Agent2 的记忆：
1. "At position 0, I saw ['chair']. I decided to forward. Reason: 探索新区域"
2. "At position 1, I saw ['lamp']. I decided to forward. Reason: 继续探索"
3. "At position 2, I saw ['cup']. I decided to backward. Reason: 避开已探索区域"
   ↑ 没有任何关于 keyboard 的信息 ❌

# 搜索 "Where is keyboard?"
# 结果：[] ❌
```

**改动后**：
```
Agent2 的记忆：
1. "At position 0, I saw ['chair']. I decided to forward. Reason: 探索新区域"
2. "At position 1, I saw ['lamp']. I decided to forward. Reason: 继续探索"
3. "At position 2, I saw ['cup']. I decided to backward. Reason: 避开已探索区域 | Context from others: Agent1: 位置3有keyboard和mouse"
   ↑ 包含了 Agent1 的消息 ✅

# 搜索 "Where is keyboard?"
# 结果：[("At position 2... Agent1: 位置3有keyboard...", 2.3)] ✅
```

---

## 🎯 改进效果

### 1. 信息完整性
- ✅ 所有消息被永久保存
- ✅ Agent可以回顾历史消息
- ✅ 信息不会丢失

### 2. 记忆质量
- ✅ Agent的记忆包含自己的经验和其他Agent的信息
- ✅ 可以通过语义搜索回忆其他Agent的发现
- ✅ 决策时可以利用更完整的信息

### 3. 协作能力
- ✅ Agent更明确地考虑其他Agent的消息
- ✅ 决策理由中更可能提到协作信息
- ✅ 避免重复探索的能力更强

### 4. 可调试性
- ✅ 可以查看完整的消息历史
- ✅ 可以验证消息是否被正确存入记忆
- ✅ 更容易分析Agent的行为

---

## 🧪 如何验证改进

### 测试1：检查消息历史

运行系统后，查看输出的 "Message history" 部分：

```
Message history (5 messages):
  1. Agent1 → all: 我在位置3发现了keyboard和mouse
  2. Agent2 → all: 收到，我正在探索位置1
  3. Agent1 → all: 位置5也有很多物体
  ...
```

### 测试2：检查记忆内容

查看 Agent 的 "Sample memories"：

```
Sample memories:
  1. At position 2, I saw ['cup']. I decided to backward. Reason: 避开已探索区域 | Context from others: Agent1: 位置3有keyboard和mouse...
  2. At position 1, I saw ['lamp']. I decided to forward. Reason: 继续探索 | Context from others: Agent1: 位置5也有很多物体...
```

**关键**：如果看到 `| Context from others:` 部分，说明消息已成功存入记忆！

### 测试3：观察决策理由

查看 Agent 的决策输出：

```
[Agent2] Decision: backward
  Reason: Agent1报告位置3有很多物体，我避开那里探索其他区域
```

如果理由中明确提到其他Agent，说明消息成功影响了决策！

---

## 📝 使用建议

### 1. 查看消息历史

在代码中可以随时访问：

```python
# 获取所有历史消息
all_messages = global_env["message_history"]

# 过滤特定Agent发送的消息
agent1_messages = [msg for msg in all_messages if msg["sender"] == "Agent1"]

# 过滤发给特定Agent的消息
to_agent2 = [msg for msg in all_messages if msg["recipient"] in ["Agent2", "all"]]
```

### 2. 搜索记忆中的消息

```python
from utils import get_embedding, search_memory

# 搜索 "keyboard在哪里"
query = "Where is the keyboard?"
query_emb = get_embedding(query)
results = search_memory(
    agent_shared["memory_index"],
    query_emb,
    agent_shared["memory_texts"],
    top_k=5
)

# 结果会包含提到 keyboard 的记忆（包括其他Agent的消息）
```

### 3. 分析Agent协作

```python
# 统计消息数量
total_msgs = len(global_env["message_history"])

# 统计每个Agent发送的消息数
from collections import Counter
msg_counts = Counter(msg["sender"] for msg in global_env["message_history"])
print(f"Agent1 sent {msg_counts['Agent1']} messages")
print(f"Agent2 sent {msg_counts['Agent2']} messages")
```

---

## 🚀 未来扩展方向

### 1. 消息优先级
为消息添加优先级字段，重要消息优先处理

### 2. 消息过期机制
为消息添加时间戳和TTL，旧消息自动过期

### 3. 消息摘要
自动生成消息历史的摘要，避免信息过载

### 4. 共享记忆池
创建全局共享记忆，所有Agent都可以检索

### 5. 消息持久化
将消息历史保存到数据库，支持长期运行

---

## 📚 相关文件

- `utils/environment.py` - 消息队列和历史记录
- `nodes.py` - UpdateMemoryNode 和 DecisionNode
- `main.py` - 调试输出
- `README.md` - 项目总体说明

---

**改进完成！** 🎉

