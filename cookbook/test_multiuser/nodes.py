"""
Multi-Agent探索系统的节点定义
"""
from pocketflow import Node
from utils import (
    call_llm,
    get_embedding,
    search_memory,
    add_to_memory,
    get_visible_objects,
    execute_action,
    add_message,
    get_messages_for
)
import yaml
import threading

# 全局锁，保护环境访问
env_lock = threading.Lock()


class PerceptionNode(Node):
    """感知节点：获取当前环境状态"""
    
    def prep(self, shared):
        return shared["agent_id"], shared["global_env"], shared["position"]
    
    def exec(self, prep_res):
        agent_id, env, position = prep_res
        
        # 线程安全地读取环境
        with env_lock:
            visible = get_visible_objects(position, env)
        
        return visible
    
    def post(self, shared, prep_res, exec_res):
        shared["visible_objects"] = exec_res
        print(f"[{shared['agent_id']}] Position {shared['position']}: sees {exec_res}")
        return "default"


class RetrieveMemoryNode(Node):
    """检索记忆节点：从FAISS检索相关历史"""
    
    def prep(self, shared):
        visible = shared["visible_objects"]
        position = shared["position"]
        
        # 构造查询文本
        query = f"What do I know about position {position} with objects {visible}?"
        return query, shared["memory_index"], shared["memory_texts"]
    
    def exec(self, prep_res):
        query, index, memory_texts = prep_res
        
        # 获取查询向量
        query_emb = get_embedding(query)
        
        # 检索记忆
        results = search_memory(index, query_emb, memory_texts, top_k=3)
        
        return results
    
    def post(self, shared, prep_res, exec_res):
        shared["retrieved_memories"] = exec_res
        
        if exec_res:
            print(f"[{shared['agent_id']}] Retrieved {len(exec_res)} memories:")
            for i, (text, dist) in enumerate(exec_res[:2], 1):
                print(f"  {i}. {text[:80]}...")
        else:
            print(f"[{shared['agent_id']}] No memories found (first time)")
        
        return "default"


class CommunicationNode(Node):
    """通信节点：读取其他agent的消息"""
    
    def prep(self, shared):
        return shared["agent_id"], shared["global_env"]
    
    def exec(self, prep_res):
        agent_id, env = prep_res
        
        # 线程安全地读取消息
        with env_lock:
            messages = get_messages_for(env, agent_id)
        
        return messages
    
    def post(self, shared, prep_res, exec_res):
        shared["other_agent_messages"] = exec_res
        
        if exec_res:
            print(f"[{shared['agent_id']}] Received {len(exec_res)} messages:")
            for msg in exec_res:
                print(f"  From {msg['sender']}: {msg['message']}")
        
        return "default"


class DecisionNode(Node):
    """决策节点：基于上下文决定下一步动作"""
    
    def prep(self, shared):
        # 收集所有决策所需的上下文
        context = {
            "agent_id": shared["agent_id"],
            "position": shared["position"],
            "visible_objects": shared["visible_objects"],
            "retrieved_memories": shared["retrieved_memories"],
            "other_agent_messages": shared["other_agent_messages"],
            "explored_objects": list(shared["explored_objects"]),
            "step_count": shared["step_count"]
        }
        return context
    
    def exec(self, context):
        # 构造决策prompt
        memories_text = "\n".join([
            f"- {text[:100]}" 
            for text, _ in context["retrieved_memories"][:3]
        ]) if context["retrieved_memories"] else "无历史记忆"
        
        messages_text = "\n".join([
            f"- {msg['sender']}: {msg['message']}"
            for msg in context["other_agent_messages"]
        ]) if context["other_agent_messages"] else "无其他agent消息"
        
        prompt = f"""你是 {context['agent_id']}，一个在XR环境中探索的智能体。

当前状态：
- 位置：{context['position']}
- 看到的物体：{context['visible_objects']}
- 已探索过的物体：{context['explored_objects']}
- 已探索步数：{context['step_count']}

历史记忆（相关的）：
{memories_text}

其他Agent消息：
{messages_text}

任务目标：尽可能探索更多新物体，避免重复探索已见过的区域。

可用动作：
- forward: 前进到下一个位置
- backward: 后退到上一个位置

请基于上述信息决策下一步动作，输出YAML格式：

```yaml
thinking: 你的思考过程（考虑是否该探索新区域，还是已探索过）
action: forward 或 backward
reason: 选择这个动作的原因
message_to_others: 想要告诉其他agent的信息（可选）
```
"""
        
        response = call_llm(prompt)
        
        # 解析YAML
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
        result = yaml.safe_load(yaml_str)
        
        # 验证必需字段
        assert isinstance(result, dict), "结果必须是字典"
        assert "action" in result, "缺少action字段"
        assert result["action"] in ["forward", "backward"], f"无效的action: {result['action']}"
        assert "reason" in result, "缺少reason字段"
        
        return result
    
    def post(self, shared, prep_res, exec_res):
        shared["action"] = exec_res["action"]
        shared["action_reason"] = exec_res.get("reason", "")
        shared["message_to_others"] = exec_res.get("message_to_others", "")
        
        print(f"[{shared['agent_id']}] Decision: {exec_res['action']}")
        print(f"  Reason: {exec_res['reason']}")
        
        return "default"


class ExecutionNode(Node):
    """执行节点：执行动作并更新环境"""
    
    def prep(self, shared):
        return shared["agent_id"], shared["action"], shared["global_env"]
    
    def exec(self, prep_res):
        agent_id, action, env = prep_res
        
        # 线程安全地更新环境
        with env_lock:
            new_position = execute_action(agent_id, action, env)
        
        return new_position
    
    def post(self, shared, prep_res, exec_res):
        # 更新位置
        shared["position"] = exec_res
        shared["step_count"] += 1
        
        # 发送消息给其他agent
        if shared.get("message_to_others"):
            agent_id = shared["agent_id"]
            message = shared["message_to_others"]
            env = shared["global_env"]
            
            with env_lock:
                # 发送给所有其他agent
                add_message(env, agent_id, "all", message)
            
            print(f"[{agent_id}] Sent message: {message}")
        
        # 更新已探索物体集合
        visible = shared["visible_objects"]
        shared["explored_objects"].update(visible)
        
        return "default"


class UpdateMemoryNode(Node):
    """更新记忆节点：将新探索信息存入FAISS"""
    
    def prep(self, shared):
        # 构造记忆文本
        memory_text = (
            f"At position {shared['position']}, "
            f"I saw {shared['visible_objects']}. "
            f"I decided to {shared['action']}. "
            f"Reason: {shared['action_reason']}"
        )
        
        return memory_text, shared["memory_index"], shared["memory_texts"]
    
    def exec(self, prep_res):
        memory_text, index, memory_texts = prep_res
        
        # 获取embedding
        embedding = get_embedding(memory_text)
        
        # 添加到记忆
        add_to_memory(index, embedding, memory_text, memory_texts)
        
        return memory_text
    
    def post(self, shared, prep_res, exec_res):
        # 记录动作历史
        shared["action_history"].append({
            "step": shared["step_count"],
            "position": shared["position"],
            "action": shared["action"],
            "visible": shared["visible_objects"]
        })
        
        print(f"[{shared['agent_id']}] Memory updated: {exec_res[:80]}...")
        
        # 判断是否继续探索
        max_steps = shared["global_env"].get("max_steps", 20)
        
        if shared["step_count"] >= max_steps:
            print(f"[{shared['agent_id']}] Reached max steps ({max_steps}), ending exploration")
            return "end"
        
        return "continue"

