"""
LLM调用工具 - 使用Google Gemini Flash
"""
from google import genai
import os


def call_llm(prompt: str) -> str:
    """
    调用Gemini LLM
    
    Args:
        prompt: 输入提示词
    
    Returns:
        LLM响应文本
    """
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY", ""),
    )
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    
    response = client.models.generate_content(
        model=model,
        contents=[prompt]
    )
    
    return response.text


if __name__ == "__main__":
    # 测试LLM调用
    test_prompt = """
你是一个探索agent。当前你看到：["chair", "table"]

请决定下一步动作：
- forward: 前进探索新区域
- backward: 后退重新查看

输出格式（YAML）：
```yaml
thinking: 你的思考过程
action: forward 或 backward
reason: 选择这个动作的原因
```
"""
    
    print("Testing LLM call...")
    response = call_llm(test_prompt)
    print(f"Response:\n{response}")

