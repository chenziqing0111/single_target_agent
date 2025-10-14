"""
Control Agent - 用户交互和流程控制（使用LLM提取基因）
"""
import asyncio
import re
from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass
import json
from openai import OpenAI

@dataclass
class SessionState:
    """会话状态"""
    state: str = "init"  # init/waiting_confirm/analyzing/completed/error
    gene: Optional[str] = None
    report: Optional[str] = None
    report_url: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

class ControlAgent:
    """控制Agent - 处理用户交互和调度分析流程"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.sessions: Dict[str, SessionState] = {}
        self.graph_runner = None
        
        # 初始化LLM客户端
        self.llm_client = OpenAI(
            api_key=self.config.get('openai_api_key', 'sk-9b3ad78d6d51431c90091b575072e62f'),
            base_url=self.config.get('openai_base_url', 'https://api.deepseek.com')
        )
    
    async def extract_gene_name(self, text: str) -> Dict[str, Any]:
        """
        使用LLM从用户输入中提取基因名
        
        Returns:
            {
                "has_gene": bool,
                "genes": List[str],
                "confidence": float,
                "explanation": str
            }
        """
        prompt = """你是一个生物医学专家，擅长识别基因名称。

任务：从用户输入中提取基因名称。

注意：
1. 基因名通常是大写字母和数字的组合，如：IL17RA, PCSK9, PD-1, EGFR, TNF-α等
2. 有些基因名包含连字符，如：PD-1, PD-L1, HER-2
3. 有些基因名包含希腊字母，如：TNF-α, IFN-γ
4. 要区分基因名和普通缩写（如OK, YES, NO, API等）
5. 如果用户提到多个基因，都要提取出来

用户输入："{}"

请以JSON格式返回：
{{
    "has_gene": true/false,
    "genes": ["基因1", "基因2"],  // 如果没有则为空列表
    "confidence": 0.0-1.0,  // 置信度
    "explanation": "简短说明"  // 如"检测到IL17RA基因"或"未发现基因名称"
}}

只返回JSON，不要其他内容。""".format(text)
        
        try:
            response = self.llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是生物医学专家，精确识别基因名称。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 低温度，更确定
                max_tokens=200
            )
            
            # 解析响应
            content = response.choices[0].message.content.strip()
            
            # 清理可能的markdown标记
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            # 解析JSON
            result = json.loads(content)
            
            # 确保返回格式正确
            return {
                "has_gene": result.get("has_gene", False),
                "genes": result.get("genes", []),
                "confidence": result.get("confidence", 0.0),
                "explanation": result.get("explanation", "")
            }
            
        except Exception as e:
            print(f"[Control Agent] LLM基因提取失败: {e}")
            # 降级到简单的正则匹配
            return self._fallback_gene_extraction(text)
    
    def _fallback_gene_extraction(self, text: str) -> Dict[str, Any]:
        """备用的简单基因提取（当LLM失败时）"""
        # 常见基因模式
        pattern = r'\b[A-Z][A-Z0-9]{1,10}(?:[-][A-Z0-9]+)?\b'
        matches = re.findall(pattern, text.upper())
        
        # 过滤非基因词
        non_genes = {'OK', 'YES', 'NO', 'API', 'HTML', 'PDF', 'URL'}
        genes = [m for m in matches if m not in non_genes and (
            any(c.isdigit() for c in m) or '-' in m or len(m) >= 3
        )]
        
        return {
            "has_gene": len(genes) > 0,
            "genes": genes,
            "confidence": 0.5,  # 备用方法置信度较低
            "explanation": f"通过模式匹配找到: {', '.join(genes)}" if genes else "未找到基因名"
        }
    
    def is_confirmation(self, text: str) -> bool:
        """检查是否是确认词"""
        confirm_words = [
            '确认', '是', '好', '开始', 'ok', 'yes', 
            '确定', '可以', '同意', '开始吧', '好的',
            'start', 'begin', 'go', '没问题'
        ]
        text_lower = text.lower()
        return any(word in text_lower for word in confirm_words)
    
    def is_rejection(self, text: str) -> bool:
        """检查是否是拒绝词"""
        reject_words = [
            '不', '否', '取消', 'no', 'cancel', 
            '算了', '不用了', '等等', '停止', 'stop'
        ]
        text_lower = text.lower()
        return any(word in text_lower for word in reject_words)
    
    async def process_message(self, message: str, session_id: str) -> Dict:
        """
        处理用户消息
        
        Args:
            message: 用户输入
            session_id: 会话ID
            
        Returns:
            响应字典
        """
        # 获取或创建会话
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        
        session = self.sessions[session_id]
        
        # 根据状态处理
        if session.state == "init":
            return await self._handle_initial(message, session, session_id)
            
        elif session.state == "waiting_confirm":
            return await self._handle_confirmation(message, session, session_id)
            
        elif session.state == "analyzing":
            return self._handle_analyzing(session)
            
        elif session.state == "completed":
            return await self._handle_completed(message, session, session_id)
            
        elif session.state == "error":
            return self._handle_error(session, session_id)
        
        else:
            # 重置状态
            session.state = "init"
            return await self._handle_initial(message, session, session_id)
    
    async def _handle_initial(self, message: str, session: SessionState, session_id: str) -> Dict:
        """处理初始状态"""
        # 使用LLM提取基因名
        extraction = await self.extract_gene_name(message)
        
        print(f"[Control Agent] 基因提取结果: {extraction}")
        
        if not extraction["has_gene"]:
            # 没有检测到基因
            return {
                "type": "need_gene",
                "message": """😊 您好！我是靶点分析助手。
                
请告诉我您想要分析的基因名称，例如：
- IL17RA（炎症相关靶点）
- PCSK9（降脂靶点）
- PD-1 或 PD-L1（免疫检查点）
- EGFR（肿瘤靶点）
- TNF-α（炎症因子）

请输入一个基因名称：""",
                "status": "waiting_input",
                "llm_explanation": extraction.get("explanation", "")
            }
        
        elif len(extraction["genes"]) > 1:
            # 检测到多个基因
            gene_list = '\n'.join([f"• {g}" for g in extraction["genes"]])
            return {
                "type": "multiple_genes",
                "message": f"""检测到多个基因：
{gene_list}

目前系统支持单个基因的深度分析。
请选择您最想分析的基因名称。""",
                "genes": extraction["genes"],
                "status": "waiting_selection",
                "confidence": extraction["confidence"]
            }
        
        else:
            # 单个基因，请求确认
            gene = extraction["genes"][0]
            session.gene = gene
            session.state = "waiting_confirm"
            
            # 根据置信度调整消息
            confidence_msg = ""
            if extraction["confidence"] < 0.8:
                confidence_msg = f"\n（识别置信度：{extraction['confidence']:.0%}，如有误请重新输入）"
            
            return {
                "type": "confirm",
                "message": f"""🎯 准备为您分析 **{gene}** 基因{confidence_msg}

将为您生成包含以下内容的深度调研报告：

📚 **文献研究**：疾病机制、治疗策略、靶点价值
🔬 **临床进展**：全球临床试验现状与关键数据
💡 **专利分析**：技术路线、竞争格局、创新趋势  
💰 **商业评估**：市场规模、竞争格局、投资价值

⏱️ 预计分析时间：5-10分钟

确认开始分析请回复"确认"，或输入其他基因名称。""",
                "gene": gene,
                "status": "waiting_confirmation",
                "confidence": extraction["confidence"]
            }
    
    async def _handle_confirmation(self, message: str, session: SessionState, session_id: str) -> Dict:
        """处理确认状态"""
        
        if self.is_confirmation(message):
            # 用户确认，开始分析
            session.state = "analyzing"
            session.timestamp = datetime.now()
            
            # 异步启动分析
            asyncio.create_task(self._run_analysis(session_id))
            
            return {
                "type": "analyzing",
                "message": f"""🚀 开始分析 {session.gene} 基因

正在执行以下步骤：
- 文献调研分析中...
- 临床试验数据收集中...
- 专利信息检索中...
- 商业价值评估中...

请稍候，我会在完成后通知您...""",
                "gene": session.gene,
                "status": "analyzing"
            }
            
        elif self.is_rejection(message):
            # 用户拒绝
            session.state = "init"
            return {
                "type": "cancelled",
                "message": "已取消分析。请输入新的基因名称，或告诉我您的需求。",
                "status": "waiting_input"
            }
            
        else:
            # 可能是新的基因名，使用LLM提取
            extraction = await self.extract_gene_name(message)
            if extraction["has_gene"] and len(extraction["genes"]) == 1:
                session.gene = extraction["genes"][0]
                session.state = "init"
                return await self._handle_initial(message, session, session_id)
            else:
                return {
                    "type": "need_confirmation",
                    "message": f"""当前准备分析：{session.gene}
                    
请回复"确认"开始分析，或输入新的基因名称。""",
                    "status": "waiting_confirmation"
                }
    
    async def _handle_completed(self, message: str, session: SessionState, session_id: str) -> Dict:
        """处理完成状态"""
        # 检查是否要分析新基因
        extraction = await self.extract_gene_name(message)
        if extraction["has_gene"]:
            # 重置状态，分析新基因
            session.state = "init"
            return await self._handle_initial(message, session, session_id)
        
        return {
            "type": "completed",
            "message": f"""✅ {session.gene} 基因分析完成！

报告已生成：{session.report_url}

您可以：
- 输入新的基因名称进行分析
- 下载当前报告
- 查看详细内容""",
            "report_url": session.report_url,
            "status": "completed"
        }
    
    def _handle_analyzing(self, session: SessionState) -> Dict:
        """处理分析中状态"""
        elapsed = (datetime.now() - session.timestamp).seconds if session.timestamp else 0
        
        return {
            "type": "in_progress",
            "message": f"""⏳ {session.gene} 基因分析进行中...

已运行：{elapsed}秒

请耐心等待，分析完成后将自动展示报告。""",
            "gene": session.gene,
            "status": "analyzing"
        }
    
    def _handle_error(self, session: SessionState, session_id: str) -> Dict:
        """处理错误状态"""
        # 重置状态
        session.state = "init"
        
        return {
            "type": "error",
            "message": f"""❌ 分析过程中出现错误

错误信息：{session.error}

请重新输入基因名称开始新的分析。""",
            "status": "error"
        }
    
    async def _run_analysis(self, session_id: str):
        """执行实际的分析流程"""
        session = self.sessions[session_id]
        
        try:
            # 导入graph runner
            from agent_core.state_machine.graph_runner import GraphRunner
            
            # 初始化runner
            if not self.graph_runner:
                self.graph_runner = GraphRunner(self.config)
            
            # 运行分析图
            print(f"[Control Agent] 开始分析 {session.gene}")
            
            result = await self.graph_runner.run({
                "gene_name": session.gene,
                "mode": "deep",
                "parallel": self.config.get("parallel", True)
            })
            
            # 保存结果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"{session.gene}_report_{timestamp}.html"
            
            # 写入文件
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(result.get("final_report", ""))
            
            # 更新会话状态
            session.state = "completed"
            session.report = result.get("final_report")
            session.report_url = report_filename
            
            print(f"[Control Agent] {session.gene} 分析完成")
            
        except Exception as e:
            print(f"[Control Agent] 分析出错: {str(e)}")
            session.state = "error"
            session.error = str(e)


# 测试函数
async def test_control_agent():
    """测试Control Agent"""
    control = ControlAgent()
    
    # 测试场景1：没有基因
    print("\n=== 测试1：没有基因 ===")
    response = await control.process_message("我想做靶点分析", "test_session_1")
    print(response["message"])
    
    # 测试场景2：有基因
    print("\n=== 测试2：有基因 ===")
    response = await control.process_message("帮我分析一下IL17RA基因", "test_session_2")
    print(response["message"])
    print(f"置信度: {response.get('confidence', 'N/A')}")
    
    # 测试场景3：复杂基因名
    print("\n=== 测试3：复杂基因名 ===")
    response = await control.process_message("我想了解TNF-α和PD-L1", "test_session_3")
    print(response["message"])
    
    # 测试场景4：模糊输入
    print("\n=== 测试4：模糊输入 ===")
    response = await control.process_message("那个降脂的PCSK什么来着", "test_session_4")
    print(response["message"])

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_control_agent())