# agent_core/clients/llm_client.py
import asyncio
from openai import OpenAI
from typing import List, Dict, Any, Optional

class LLMClient:
    """LLM客户端 - 支持多种LLM API"""
    
    def __init__(self, api_key: str = "sk-9b3ad78d6d51431c90091b575072e62f", 
                 base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-reasoner"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        
    async def generate_response(self, prompt: str, 
                              system_message: str = "你是一个专业的生物医学研究助手") -> str:
        """生成响应"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM API调用失败: {e}")
            raise e
    
    def generate_response_sync(self, prompt: str, 
                             system_message: str = "你是一个专业的生物医学研究助手") -> str:
        """同步生成响应"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM API调用失败: {e}")
            raise e


# 保持向后兼容
client = OpenAI(api_key="sk-9b3ad78d6d51431c90091b575072e62f", base_url="https://api.deepseek.com")

def call_llm(prompt: str) -> str:
    """向后兼容的函数接口"""
    llm_client = LLMClient()
    return llm_client.generate_response_sync(prompt)