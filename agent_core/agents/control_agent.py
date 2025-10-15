"""
Control Agent - 用户交互和流程控制（支持多轮对话+LLM提取基因+LangGraph分析）
"""
import asyncio
import re
from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass, field
import json
from openai import OpenAI

@dataclass
class SessionState:
    """增强的会话状态（支持多轮对话）"""
    session_id: str
    state: str = "init"  # init/waiting_confirm/analyzing/completed/error
    gene: Optional[str] = None
    genes: List[str] = field(default_factory=list)  # 历史提到的所有基因
    report: Optional[str] = None
    report_url: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    # 多轮对话支持
    messages: List[Dict[str, str]] = field(default_factory=list)  # 对话历史
    context: Dict[str, Any] = field(default_factory=dict)  # 额外上下文

class ControlAgent:
    """控制Agent - 处理用户交互、多轮对话和调度分析流程"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.sessions: Dict[str, SessionState] = {}
        self.graph_runner = None
        
        # 初始化LLM客户端
        self.llm_client = OpenAI(
            api_key=self.config.get('openai_api_key', 'sk-9b3ad78d6d51431c90091b575072e62f'),
            base_url=self.config.get('openai_base_url', 'https://api.deepseek.com')
        )
    
    def get_or_create_session(self, session_id: str) -> SessionState:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id=session_id)
        return self.sessions[session_id]
    
    async def extract_gene_name(self, text: str, context: List[Dict] = None) -> Dict[str, Any]:
        """
        使用LLM从用户输入中提取基因名（支持上下文）
        
        Args:
            text: 用户输入
            context: 对话历史上下文
            
        Returns:
            提取结果字典
        """
        # 构建上下文提示
        context_prompt = ""
        if context and len(context) > 0:
            recent_genes = set()
            for msg in context[-6:]:  # 最近3轮对话
                if msg.get("genes"):
                    recent_genes.update(msg.get("genes", []))
            if recent_genes:
                context_prompt = f"\n上下文：之前讨论过的基因包括：{', '.join(recent_genes)}"
        
        prompt = f"""你是一个生物医学专家，擅长识别基因名称。

任务：从用户输入中提取基因名称。{context_prompt}

注意：
1. 基因名通常是大写字母和数字的组合，如：IL17RA, PCSK9, PD-1, EGFR, TNF-α等
2. 有些基因名包含连字符，如：PD-1, PD-L1, HER-2
3. 有些基因名包含希腊字母，如：TNF-α, IFN-γ
4. 要区分基因名和普通缩写（如OK, YES, NO, API等）
5. 如果用户提到多个基因，都要提取出来
6. 如果用户说"它"、"这个基因"等代词，结合上下文判断是否指之前提到的基因

用户输入："{text}"

请以JSON格式返回：
{{
    "has_gene": true/false,
    "genes": ["基因1", "基因2"],  // 如果没有则为空列表
    "confidence": 0.0-1.0,  // 置信度
    "explanation": "简短说明"  // 如"检测到IL17RA基因"或"未发现基因名称"
}}

只返回JSON，不要其他内容。"""
        
        try:
            response = self.llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是生物医学专家，精确识别基因名称。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            
            # 清理markdown标记
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content)
            
            return {
                "has_gene": result.get("has_gene", False),
                "genes": result.get("genes", []),
                "confidence": result.get("confidence", 0.0),
                "explanation": result.get("explanation", "")
            }
            
        except Exception as e:
            print(f"[Control Agent] LLM基因提取失败: {e}")
            return self._fallback_gene_extraction(text)
    
    def _fallback_gene_extraction(self, text: str) -> Dict[str, Any]:
        """备用的简单基因提取（当LLM失败时）"""
        pattern = r'\b[A-Z][A-Z0-9]{1,10}(?:[-][A-Z0-9]+)?\b'
        matches = re.findall(pattern, text.upper())
        
        non_genes = {'OK', 'YES', 'NO', 'API', 'HTML', 'PDF', 'URL', 'CSV'}
        genes = [m for m in matches if m not in non_genes and (
            any(c.isdigit() for c in m) or '-' in m or len(m) >= 3
        )]
        
        return {
            "has_gene": len(genes) > 0,
            "genes": genes,
            "confidence": 0.5,
            "explanation": f"通过模式匹配找到: {', '.join(genes)}" if genes else "未找到基因名"
        }
    
    def is_confirmation(self, text: str) -> bool:
        """检查是否是确认词"""
        confirm_words = [
            '确认', '是', '好', '开始', 'ok', 'yes', 
            '确定', '可以', '同意', '开始吧', '好的',
            'start', 'begin', 'go', '没问题', '分析'
        ]
        text_lower = text.lower()
        return any(word in text_lower for word in confirm_words)
    
    def is_rejection(self, text: str) -> bool:
        """检查是否是拒绝词"""
        reject_words = [
            '不是', '否', '取消', 'no', 'cancel', 
            '算了', '不用了', '等等', '停止', 'stop'
        ]
        text_lower = text.lower()
        return any(word in text_lower for word in reject_words)
    
    async def process_message(self, message: str, session_id: str, context: Dict = None) -> Dict:
        """
        处理用户消息（支持多轮对话）
        
        Args:
            message: 用户输入
            session_id: 会话ID
            context: 额外的上下文信息
            
        Returns:
            响应字典
        """
        # 获取或创建会话
        session = self.get_or_create_session(session_id)
        session.updated_at = datetime.now()
        
        # 添加用户消息到历史
        session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # 更新上下文
        if context:
            session.context.update(context)
        
        # 根据状态处理
        if session.state == "init":
            response = await self._handle_initial(message, session, session_id)
            
        elif session.state == "waiting_confirm":
            response = await self._handle_confirmation(message, session, session_id)
            
        elif session.state == "analyzing":
            response = self._handle_analyzing(session)
            
        elif session.state == "completed":
            response = await self._handle_completed(message, session, session_id)
            
        elif session.state == "error":
            response = self._handle_error(session, session_id)
        
        else:
            session.state = "init"
            response = await self._handle_initial(message, session, session_id)
        
        # 添加助手响应到历史
        session.messages.append({
            "role": "assistant",
            "content": response.get("message", ""),
            "timestamp": datetime.now().isoformat(),
            "genes": response.get("genes", [])
        })
        
        # 限制历史长度
        if len(session.messages) > 30:
            session.messages = session.messages[-30:]
        
        return response
    
    async def _handle_initial(self, message: str, session: SessionState, session_id: str) -> Dict:
        """处理初始状态（支持多轮对话上下文）"""
        
        # 使用LLM提取基因名，传入历史上下文
        extraction = await self.extract_gene_name(message, session.messages)
        
        print(f"[Control Agent] 基因提取结果: {extraction}")
        
        # 检查是否在询问之前的基因
        message_lower = message.lower()
        if any(word in message_lower for word in ['之前', '刚才', '上次', '那个基因']):
            if session.genes:
                # 有历史基因记录
                return {
                    "type": "recall",
                    "message": f"""我记得之前讨论过以下基因：
{chr(10).join(['• ' + g for g in session.genes])}

您想继续分析哪个基因？或者要分析新的基因？""",
                    "genes": session.genes,
                    "status": "waiting_selection"
                }
        
        if not extraction["has_gene"]:
            # 根据对话历史调整响应
            if len(session.messages) > 2:
                # 有对话历史
                return {
                    "type": "need_gene",
                    "message": """我需要知道您想分析的基因名称。

请直接告诉我基因名，例如：
• IL17RA、PCSK9、PD-1
• EGFR、BRCA1、TP53

或者继续我们之前的讨论？""",
                    "status": "waiting_input"
                }
            else:
                # 首次对话
                return {
                    "type": "need_gene",
                    "message": """😊 您好！我是靶点分析助手。
                    
请告诉我您想要分析的基因名称，例如：
• IL17RA（炎症相关靶点）
• PCSK9（降脂靶点）
• PD-1 或 PD-L1（免疫检查点）
• EGFR（肿瘤靶点）
• TNF-α（炎症因子）

请输入一个基因名称：""",
                    "status": "waiting_input"
                }
        
        elif len(extraction["genes"]) > 1:
            # 多个基因
            gene_list = '\n'.join([f"• {g}" for g in extraction["genes"]])
            # 更新会话基因列表
            session.genes.extend(extraction["genes"])
            session.genes = list(set(session.genes))
            
            return {
                "type": "multiple_genes",
                "message": f"""检测到多个基因：
{gene_list}

目前系统支持单个基因的深度分析。
请选择您最想分析的基因名称，或回复"第一个"。""",
                "genes": extraction["genes"],
                "status": "waiting_selection",
                "confidence": extraction["confidence"]
            }
        
        else:
            # 单个基因
            gene = extraction["genes"][0]
            session.gene = gene
            session.genes.append(gene)
            session.genes = list(set(session.genes))
            session.state = "waiting_confirm"
            
            # 根据历史调整消息
            history_msg = ""
            if len(session.messages) > 4:
                history_msg = "\n\n基于我们之前的讨论，我会特别关注您感兴趣的方面。"
            
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
💰 **商业评估**：市场规模、竞争格局、投资价值{history_msg}

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
            
            # 异步启动分析（重要：调用LangGraph）
            asyncio.create_task(self._run_analysis(session_id))
            
            return {
                "type": "analyzing",
                "message": f"""🚀 开始分析 {session.gene} 基因

正在执行以下步骤：
• 文献调研分析中...
• 临床试验数据收集中...
• 专利信息检索中...
• 商业价值评估中...

请稍候，分析完成后会自动展示报告...""",
                "gene": session.gene,
                "status": "analyzing",
                "task_started": True
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
            # 可能是新的基因名
            extraction = await self.extract_gene_name(message, session.messages)
            if extraction["has_gene"] and len(extraction["genes"]) == 1:
                # 切换到新基因
                session.gene = extraction["genes"][0]
                session.genes.append(session.gene)
                session.genes = list(set(session.genes))
                session.state = "init"
                return await self._handle_initial(message, session, session_id)
            else:
                return {
                    "type": "need_confirmation",
                    "message": f"""当前准备分析：**{session.gene}**
                    
请回复"确认"开始分析，或输入新的基因名称。""",
                    "gene": session.gene,
                    "status": "waiting_confirmation"
                }
    
    async def _handle_completed(self, message: str, session: SessionState, session_id: str) -> Dict:
        """处理完成状态"""
        # 检查是否要分析新基因
        extraction = await self.extract_gene_name(message, session.messages)
        if extraction["has_gene"]:
            session.state = "init"
            return await self._handle_initial(message, session, session_id)
        
        # 检查是否询问其他基因
        if "其他" in message or "还有" in message:
            other_genes = [g for g in session.genes if g != session.gene]
            if other_genes:
                return {
                    "type": "suggest",
                    "message": f"""✅ {session.gene} 分析已完成！

您还查询过这些基因：
{chr(10).join(['• ' + g for g in other_genes])}

需要分析其中的某个基因吗？""",
                    "genes": other_genes,
                    "report_url": session.report_url,
                    "status": "completed"
                }
        
        return {
            "type": "completed",
            "message": f"""✅ {session.gene} 基因分析完成！

报告已生成：{session.report_url}

您可以：
• 输入新的基因名称进行分析
• 下载当前报告查看详细内容
• 询问关于该基因的具体问题""",
            "report_url": session.report_url,
            "status": "completed"
        }
    
    def _handle_analyzing(self, session: SessionState) -> Dict:
        """处理分析中状态"""
        elapsed = (datetime.now() - session.timestamp).seconds if session.timestamp else 0
        minutes = elapsed // 60
        seconds = elapsed % 60
        
        return {
            "type": "in_progress",
            "message": f"""⏳ {session.gene} 基因分析进行中...

已运行：{minutes}分{seconds}秒

请耐心等待，分析完成后将自动展示报告。
您也可以继续提问，我会在分析完成后回复。""",
            "gene": session.gene,
            "status": "analyzing"
        }
    
    def _handle_error(self, session: SessionState, session_id: str) -> Dict:
        """处理错误状态"""
        session.state = "init"
        
        return {
            "type": "error",
            "message": f"""❌ 分析过程中出现错误

错误信息：{session.error}

请重新输入基因名称开始新的分析，或尝试分析其他基因。""",
            "status": "error"
        }
    
    async def _run_analysis(self, session_id: str):
        """
        执行实际的分析流程（调用LangGraph）
        这是核心分析功能！
        """
        session = self.sessions[session_id]
        
        try:
            # 导入graph runner
            from agent_core.state_machine.graph_runner import GraphRunner
            
            # 初始化runner
            if not self.graph_runner:
                self.graph_runner = GraphRunner(self.config)
            
            print(f"[Control Agent] 开始分析 {session.gene}")
            
            # 运行分析图（LangGraph）
            result = await self.graph_runner.run({
                "gene_name": session.gene,
                "mode": "deep",
                "parallel": self.config.get("parallel", True),
                "session_context": {
                    "history_genes": session.genes,
                    "conversation_count": len(session.messages)
                }
            })
            
            # 保存结果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"reports/{session.gene}_report_{timestamp}.html"
            
            # 确保目录存在
            import os
            os.makedirs("reports", exist_ok=True)
            
            # 写入文件
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(result.get("final_report", ""))
            
            # 更新会话状态
            session.state = "completed"
            session.report = result.get("final_report")
            session.report_url = report_filename
            
            print(f"[Control Agent] {session.gene} 分析完成，报告已保存至 {report_filename}")
            
        except ImportError as e:
            print(f"[Control Agent] 导入GraphRunner失败: {str(e)}")
            session.state = "error"
            session.error = "分析模块未正确安装"
            
        except Exception as e:
            print(f"[Control Agent] 分析出错: {str(e)}")
            import traceback
            traceback.print_exc()
            session.state = "error"
            session.error = str(e)
    
    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """获取会话历史"""
        session = self.get_or_create_session(session_id)
        return session.messages
    
    def clear_session(self, session_id: str):
        """清空会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]


# 测试函数
async def test_multiround_control():
    """测试多轮对话的Control Agent"""
    control = ControlAgent()
    session_id = "test_multi_123"
    
    print("=== 测试多轮对话+LLM+LangGraph ===\n")
    
    # 第一轮
    print("用户：你好")
    r1 = await control.process_message("你好", session_id)
    print(f"助手：{r1['message'][:100]}...\n")
    
    # 第二轮
    print("用户：我想分析IL17RA")
    r2 = await control.process_message("我想分析IL17RA", session_id)
    print(f"助手：{r2['message'][:100]}...")
    print(f"识别的基因：{r2.get('gene')}\n")
    
    # 第三轮
    print("用户：还有PCSK9")
    r3 = await control.process_message("还有PCSK9", session_id)
    print(f"助手：{r3['message'][:100]}...")
    print(f"基因列表：{r3.get('genes')}\n")
    
    # 第四轮
    print("用户：先分析第一个")
    r4 = await control.process_message("先分析第一个", session_id)
    print(f"助手：{r4['message'][:100]}...\n")
    
    # 第五轮
    print("用户：确认")
    r5 = await control.process_message("确认", session_id)
    print(f"助手：{r5['message'][:100]}...")
    print(f"任务状态：{r5.get('status')}\n")
    
    # 查看历史
    history = control.get_conversation_history(session_id)
    print(f"对话历史：{len(history)}条消息")
    print(f"涉及的基因：{control.sessions[session_id].genes}")


if __name__ == "__main__":
    asyncio.run(test_multiround_control())