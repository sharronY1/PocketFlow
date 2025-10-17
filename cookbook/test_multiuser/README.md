# Multi-Agent XR Environment Exploration

一个基于PocketFlow的多智能体协作环境探索系统，展示了两个Agent在XR虚拟环境中自主探索并通过RAG记忆系统避免重复探索。

## 系统特点

- **多Agent协作**：两个独立的Agent并行探索同一环境
- **RAG记忆系统**：使用FAISS向量数据库存储和检索探索历史
- **Agent间通信**：通过消息队列共享发现的信息
- **自主决策**：基于LLM的智能决策，综合考虑当前状态、历史记忆和其他Agent信息
- **简单动作空间**：前进/后退两个基础动作

## 项目结构

```
test_multiuser/
├── docs/
│   └── design.md          # 详细设计文档
├── utils/
│   ├── __init__.py
│   ├── call_llm.py        # LLM调用（Gemini Flash）
│   ├── embedding.py       # 文本embedding（sentence-transformers）
│   ├── memory.py          # FAISS记忆管理
│   └── environment.py     # 环境模拟
├── nodes.py               # Agent节点定义
├── flow.py                # Flow定义
├── main.py                # 主程序
├── requirements.txt       # 依赖
└── README.md
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

## 运行

```bash
python main.py
```

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

### 1. 简单而有效的RAG

使用轻量级模型（all-MiniLM-L6-v2）和FAISS实现快速记忆检索：
- 每次决策前检索相关历史
- 避免重复探索已知区域
- 存储成本低，检索速度快

### 2. Agent间异步通信

通过消息队列实现：
- Agent可以分享发现
- 避免冲突和重复工作
- 松耦合设计，易于扩展

### 3. 线程安全

使用锁保护共享资源：
- 环境状态访问
- 消息队列读写
- 位置更新

### 4. LLM驱动的智能决策

每个决策综合考虑：
- 当前观察（可见物体）
- 历史记忆（之前探索过的区域）
- 其他Agent消息（避免重复）
- 探索目标（最大化新物体）

## 扩展方向

1. **更多动作**：左转、右转、交互等
2. **更复杂环境**：2D/3D空间、动态物体
3. **更多Agent**：支持>2个Agent协作
4. **任务导向**：寻找特定物体、完成特定任务
5. **可视化**：实时显示Agent位置和探索进度
6. **持久化**：保存探索历史到数据库

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

