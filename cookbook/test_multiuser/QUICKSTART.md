# 快速启动指南

## 1. 安装依赖

```bash
cd cookbook/test_multiuser
pip install -r requirements.txt
```

**注意**：首次运行会自动下载embedding模型（约80MB）

## 2. 设置API密钥

### Windows PowerShell
```powershell
$env:GEMINI_API_KEY="your-gemini-api-key-here"
```

### Linux/Mac
```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

**获取API密钥**：访问 [Google AI Studio](https://aistudio.google.com/app/apikey)

## 3. 测试工具函数（可选）

```bash
python test_utils.py
```

这会测试：
- ✓ 环境模拟
- ✓ Embedding生成
- ✓ FAISS记忆系统
- ✓ LLM调用

## 4. 运行主程序

```bash
python main.py
```

## 预期输出

```
============================================================
Multi-Agent XR Environment Exploration System
============================================================

[System] Creating environment...
[System] Environment created with 10 positions

[System] Environment layout:
  Position 0: ['chair', 'table']
  Position 1: ['lamp', 'book', 'cup']
  ...

[System] Starting 2 agents...

============================================================
Starting Agent1...
============================================================

[Agent1] Position 0: sees ['chair', 'table']
[Agent1] No memories found (first time)
[Agent1] Decision: forward
  Reason: No objects explored yet, moving forward to discover new items
...

============================================================
Agent1 Exploration Summary
============================================================
Total steps: 15
Final position: 7
Unique objects explored: 18
Objects: {'chair', 'table', 'lamp', 'book', ...}
Memories stored: 15
============================================================

============================================================
FINAL SYSTEM SUMMARY
============================================================
Total execution time: 45.23 seconds
Total unique objects explored by all agents: 25
Coverage: 25 / 30 objects
Final agent positions:
  Agent1: position 7
  Agent2: position 5
============================================================

[System] Exploration completed!
```

## 系统工作流程

### 每个Agent的决策循环

```
1. Perception (感知)
   ↓
2. RetrieveMemory (从FAISS检索相关记忆)
   ↓
3. Communication (读取其他Agent消息)
   ↓
4. Decision (LLM决策：forward/backward)
   ↓
5. Execution (执行动作，更新位置)
   ↓
6. UpdateMemory (存储新记忆到FAISS)
   ↓
   └─→ 继续循环或结束
```

### Agent协作机制

- **独立探索**：每个Agent有自己的记忆系统
- **消息共享**：Agent可以告诉其他Agent发现了什么
- **避免重复**：通过RAG检索历史，避免重复探索
- **并行运行**：两个Agent同时运行，使用线程

## 关键文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 主程序入口，创建环境和启动Agent |
| `flow.py` | 定义Agent的决策循环Flow |
| `nodes.py` | 6个节点的实现 |
| `utils/call_llm.py` | LLM调用（Gemini） |
| `utils/embedding.py` | 文本embedding |
| `utils/memory.py` | FAISS记忆管理 |
| `utils/environment.py` | 环境模拟 |
| `docs/design.md` | 详细设计文档 |

## 常见问题

### Q: 为什么选择Gemini Flash？
A: 最快速且成本最低的商用LLM之一，适合高频调用场景。

### Q: 为什么用FAISS而不是其他向量数据库？
A: FAISS简单、快速、无需服务器，适合原型开发。

### Q: Agent之间如何避免冲突？
A: 使用线程锁保护共享资源（环境状态、消息队列）。

### Q: 能否增加更多Agent？
A: 可以！只需在`main.py`中创建更多线程即可。

### Q: 如何可视化探索过程？
A: 可以扩展添加web界面或使用matplotlib绘制实时图表。

## 下一步

1. 查看 `docs/design.md` 了解完整设计
2. 修改 `utils/environment.py` 创建更复杂的环境
3. 扩展 `nodes.py` 添加更多动作（左转、右转、交互）
4. 实验不同的LLM模型和提示词

## 故障排除

### 错误：`ModuleNotFoundError: No module named 'sentence_transformers'`
```bash
pip install sentence-transformers
```

### 错误：`ModuleNotFoundError: No module named 'faiss'`
```bash
pip install faiss-cpu
```

### 错误：LLM调用失败
- 检查API密钥是否正确设置
- 确认网络连接正常
- 查看是否超出API配额

### 模型下载慢
首次运行会下载embedding模型，可能需要几分钟。使用国内镜像：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

---

**有问题？** 查看完整文档 `README.md` 或设计文档 `docs/design.md`

