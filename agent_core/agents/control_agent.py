"""
Control Agent - 无状态的基因分析控制器（自管理缓存）
"""
import asyncio
import json
import os
import pickle
from typing import Dict, List, Optional, Any
from datetime import datetime
from openai import OpenAI
import threading


class ControlAgent:
    """无状态的Control Agent - 自管理缓存"""
    
    # 类级别的缓存（所有实例共享）
    _cache_store = {}
    _cache_dir = "agent_cache"
    
    def __init__(self, config=None):
        self.config = config or {}
        self.graph_runner = None
        
        # 初始化LLM客户端
        self.llm_client = OpenAI(
            api_key=self.config.get('openai_api_key', 'sk-9b3ad78d6d51431c90091b575072e62f'),
            base_url=self.config.get('openai_base_url', 'https://api.deepseek.com')
        )
        
        # 初始化缓存目录
        self._init_cache_dir()
    
    def _init_cache_dir(self):
        """初始化缓存目录"""
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir, exist_ok=True)
            print(f"[Control Agent] 创建缓存目录: {self._cache_dir}")
    
    # ========== 缓存管理方法 ==========
    def cache_set(self, key: str, value: Any, timeout: int = 3600) -> bool:
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            timeout: 过期时间（秒），默认1小时
        """
        try:
            # 内存缓存
            self._cache_store[key] = {
                'value': value,
                'expire_at': datetime.now().timestamp() + timeout if timeout else None
            }
            
            # 同时持久化到文件（可选）
            if self.config.get('persistent_cache', True):
                cache_file = os.path.join(self._cache_dir, f"{key}.cache")
                with open(cache_file, 'wb') as f:
                    pickle.dump(self._cache_store[key], f)
            
            print(f"[Cache] 设置缓存: {key}")
            return True
            
        except Exception as e:
            print(f"[Cache] 设置缓存失败: {e}")
            return False
    
    def cache_get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存
        
        Args:
            key: 缓存键
            default: 默认值
        """
        try:
            # 先尝试内存缓存
            if key in self._cache_store:
                cache_data = self._cache_store[key]
                # 检查是否过期
                if cache_data['expire_at'] and datetime.now().timestamp() > cache_data['expire_at']:
                    print(f"[Cache] 缓存已过期: {key}")
                    del self._cache_store[key]
                    return default
                print(f"[Cache] 命中内存缓存: {key}")
                return cache_data['value']
            
            # 尝试从文件加载
            if self.config.get('persistent_cache', True):
                cache_file = os.path.join(self._cache_dir, f"{key}.cache")
                if os.path.exists(cache_file):
                    with open(cache_file, 'rb') as f:
                        cache_data = pickle.load(f)
                        # 检查是否过期
                        if cache_data['expire_at'] and datetime.now().timestamp() > cache_data['expire_at']:
                            print(f"[Cache] 文件缓存已过期: {key}")
                            os.remove(cache_file)
                            return default
                        # 加载到内存
                        self._cache_store[key] = cache_data
                        print(f"[Cache] 命中文件缓存: {key}")
                        return cache_data['value']
            
            print(f"[Cache] 未命中: {key}")
            return default
            
        except Exception as e:
            print(f"[Cache] 获取缓存失败: {e}")
            return default
    
    def cache_delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            # 删除内存缓存
            if key in self._cache_store:
                del self._cache_store[key]
            
            # 删除文件缓存
            cache_file = os.path.join(self._cache_dir, f"{key}.cache")
            if os.path.exists(cache_file):
                os.remove(cache_file)
            
            print(f"[Cache] 删除缓存: {key}")
            return True
            
        except Exception as e:
            print(f"[Cache] 删除缓存失败: {e}")
            return False
    
    def cache_clear(self) -> bool:
        """清空所有缓存"""
        try:
            # 清空内存
            self._cache_store.clear()
            
            # 清空文件
            if os.path.exists(self._cache_dir):
                for file in os.listdir(self._cache_dir):
                    if file.endswith('.cache'):
                        os.remove(os.path.join(self._cache_dir, file))
            
            print("[Cache] 清空所有缓存")
            return True
            
        except Exception as e:
            print(f"[Cache] 清空缓存失败: {e}")
            return False
    
    async def process_message(self, message: str, messages_history: List[Dict], context: Dict = None) -> Dict:
        """
        处理用户消息（无状态）
        
        Args:
            message: 用户新消息
            messages_history: 完整的对话历史（DeepSeek格式）
            context: 额外上下文（如task_id等）
            
        Returns:
            响应字典，包含回复和动作
        """
        # 构建完整的消息列表（包含新消息）
        messages = messages_history
        messages.append({"role": "user", "content": message})
        
        # 使用LLM分析当前状态和意图
        analysis = await self.analyze_conversation(messages, context)
        
        # 根据分析结果执行相应动作
        response = await self.execute_action(analysis, context)
        
        # 添加助手回复到消息历史
        response['message_to_add'] = {
            "role": "assistant",
            "content": response['message']
        }
        
        return response
    
    async def analyze_conversation(self, messages: List[Dict], context: Dict = None) -> Dict:
        """
        使用LLM分析对话状态和用户意图
        
        Returns:
            分析结果字典
        """
        system_prompt = """你是一个基因分析助手，帮助用户分析基因靶点。

基于对话历史，分析当前状态并决定下一步动作。

分析要点：
1. 识别用户提到的基因名（如IL17RA, PCSK9, PD-1等）
2. 判断对话处于什么阶段：
   - 初始阶段：用户刚开始对话或询问
   - 基因识别：用户提到了基因名，需要确认
   - 等待确认：已经询问用户是否分析，等待确认
   - 已确认：用户确认要分析
   - 分析中：正在进行分析
   - 已完成：分析已完成
3. 判断用户意图：
   - 想分析新基因
   - 确认/拒绝分析
   - 询问进度
   - 查看结果
   - 闲聊

返回JSON格式：
{
    "current_stage": "初始阶段|基因识别|等待确认|已确认|分析中|已完成",
    "user_intent": "分析基因|确认|拒绝|查询进度|查看结果|闲聊|其他",
    "genes_mentioned": ["基因1", "基因2"],
    "is_confirmation": true/false,
    "is_rejection": true/false,
    "current_gene": "正在处理的基因名",
    "next_action": "request_gene|confirm_gene|start_analysis|show_progress|show_results|chat",
    "confidence": 0.0-1.0
}"""

        try:
            response = self.llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages  # 展开完整对话历史
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # 添加context中的信息
            if context:
                if context.get('current_gene'):
                    analysis['current_gene'] = context['current_gene']
                if context.get('task_id'):
                    analysis['task_id'] = context['task_id']
            
            print(f"[Control Agent] 分析结果: {analysis}")
            return analysis
            
        except Exception as e:
            print(f"[Control Agent] LLM分析失败: {e}")
            # 返回默认分析结果
            return {
                "current_stage": "初始阶段",
                "user_intent": "其他",
                "genes_mentioned": [],
                "next_action": "request_gene",
                "error": str(e)
            }
    
    async def execute_action(self, analysis: Dict, context: Dict = None) -> Dict:
        """
        根据分析结果执行动作
        
        Args:
            analysis: LLM分析结果
            context: 上下文信息
            
        Returns:
            响应字典
        """
        action = analysis.get('next_action', 'chat')
        
        if action == 'request_gene':
            return self._request_gene_input()
            
        elif action == 'confirm_gene':
            genes = analysis.get('genes_mentioned', [])
            if len(genes) == 1:
                return self._confirm_gene_analysis(genes[0], analysis.get('confidence', 0.8))
            elif len(genes) > 1:
                return self._handle_multiple_genes(genes)
            else:
                return self._request_gene_input()
                
        elif action == 'start_analysis':
            gene = analysis.get('current_gene')
            if not gene and analysis.get('genes_mentioned'):
                gene = analysis['genes_mentioned'][0]
            
            if gene:
                # 检查缓存
                cached_report = await self._check_cache(gene)
                if cached_report:
                    return self._return_cached_report(gene, cached_report)
                
                # 启动新分析
                task_id = self._start_analysis_task(gene, context)
                return self._analysis_started(gene, task_id)
            else:
                return self._request_gene_input()
                
        elif action == 'show_progress':
            return await self._check_analysis_progress(context)
            
        elif action == 'show_results':
            return await self._show_results(context)
            
        else:
            # 默认聊天响应
            return self._chat_response(analysis)
    
    def _request_gene_input(self) -> Dict:
        """请求用户输入基因名"""
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
    
    def _confirm_gene_analysis(self, gene: str, confidence: float) -> Dict:
        """确认基因分析"""
        confidence_msg = ""
        if confidence < 0.8:
            confidence_msg = f"\n（识别置信度：{confidence:.0%}，如有误请重新输入）"
        
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
            "confidence": confidence
        }
    
    def _handle_multiple_genes(self, genes: List[str]) -> Dict:
        """处理多个基因的情况"""
        gene_list = '\n'.join([f"• {g}" for g in genes])
        return {
            "type": "multiple_genes",
            "message": f"""检测到多个基因：
{gene_list}

目前系统支持单个基因的深度分析。
请选择您最想分析的基因名称。""",
            "genes": genes,
            "status": "waiting_selection"
        }
    
    async def _check_cache(self, gene: str) -> Optional[Dict]:
        """检查是否有缓存的报告"""
        # 生成缓存key（基因名+年月）
        cache_key = f"gene_report_{gene}_{datetime.now().strftime('%Y-%m')}"
        
        # 使用自己的缓存方法
        cached = self.cache_get(cache_key)
        if cached:
            print(f"[Control Agent] 找到缓存报告: {gene}")
            return cached
        
        return None
    
    def _return_cached_report(self, gene: str, cached_report: Dict) -> Dict:
        """返回缓存的报告"""
        return {
            "type": "cached_result",
            "message": f"""✅ 找到 {gene} 基因的最新分析报告！

📅 生成时间：{cached_report.get('generated_at', '最近')}
📄 报告链接：{cached_report.get('report_url', '#')}

这是本月最新的分析报告，包含最新的研究进展和临床数据。

您可以：
• 查看完整报告
• 分析其他基因
• 如需重新生成，请说"强制刷新" """,
            "gene": gene,
            "report_url": cached_report.get('report_url'),
            "from_cache": True,
            "status": "completed"
        }
    
    def _start_analysis_task(self, gene: str, context: Dict = None) -> str:
        """启动分析任务"""
        # 生成任务ID
        task_id = f"{gene}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"[Control Agent] 启动分析任务: {gene} (ID: {task_id})")
        
        # 缓存任务状态（让status接口立刻可查）
        self.cache_set(f"task_status_{task_id}", "running", timeout=3600)

        #定义一个任务函数，让它自己建 event loop 并运行异步逻辑
        def run_in_thread():
            try:
                asyncio.run(self._run_analysis(gene, task_id))
            except Exception as e:
                print(f"[Control Agent] 后台任务失败: {e}")
                self.cache_set(f"task_status_{task_id}", f"error: {e}", timeout=3600)

        # 启动后台线程（daemon=True：不会阻塞Django退出）
        threading.Thread(target=run_in_thread, daemon=True).start()

        return task_id
    
    def _analysis_started(self, gene: str, task_id: str) -> Dict:
        """分析已启动的响应"""
        return {
            "type": "analyzing",
            "message": f"""🚀 开始分析 {gene} 基因

正在执行以下步骤：
• 文献调研分析中...
• 临床试验数据收集中...
• 专利信息检索中...
• 商业价值评估中...

请稍候，我会在完成后通知您...""",
            "gene": gene,
            "task_id": task_id,
            "task_started": True,
            "status": "analyzing"
        }
    
    async def _check_analysis_progress(self, context: Dict) -> Dict:
        """检查分析进度"""
        task_id = context.get('task_id')
        gene = context.get('current_gene')
        
        if not task_id:
            return {
                "type": "no_task",
                "message": "当前没有正在运行的分析任务。请输入基因名称开始新的分析。",
                "status": "waiting_input"
            }
        
        # 使用自己的缓存检查任务状态
        task_status = self.cache_get(f"task_status_{task_id}")
        
        if task_status == 'completed':
            return await self._show_results(context)
        else:
            # 计算运行时间
            start_time = context.get('task_start_time')
            elapsed = "几"
            if start_time:
                elapsed = int((datetime.now() - datetime.fromisoformat(start_time)).seconds)
            
            return {
                "type": "in_progress", 
                "message": f"""⏳ {gene} 基因分析进行中...

已运行：{elapsed}秒

正在收集和分析数据，请耐心等待...""",
                "gene": gene,
                "status": "analyzing"
            }
    
    async def _show_results(self, context: Dict) -> Dict:
        """显示分析结果"""
        gene = context.get('current_gene')
        task_id = context.get('task_id')
        
        # 使用自己的缓存获取结果
        cache_key = f"gene_report_{gene}_{datetime.now().strftime('%Y-%m')}"
        report = self.cache_get(cache_key)
        
        if report:
            return {
                "type": "completed",
                "message": f"""✅ {gene} 基因分析完成！

📄 报告已生成：{report.get('report_url', '#')}
📅 生成时间：{report.get('generated_at', '刚刚')}

报告包含：
• 文献综述与机制研究
• 全球临床试验进展
• 专利布局与技术趋势
• 商业价值与投资分析

您可以：
• 下载完整报告
• 分析其他基因""",
                "gene": gene,
                "report_url": report.get('report_url'),
                "status": "completed"
            }
        else:
            return {
                "type": "not_ready",
                "message": f"{gene} 基因分析还在进行中，请稍后查看。",
                "status": "analyzing"
            }
    
    def _chat_response(self, analysis: Dict) -> Dict:
        """通用聊天响应"""
        # 根据分析结果生成合适的回复
        stage = analysis.get('current_stage', '')
        intent = analysis.get('user_intent', '')
        
        if intent == '闲聊':
            return {
                "type": "chat",
                "message": "我是基因分析助手，专注于帮您分析基因靶点。请问您想了解哪个基因呢？",
                "status": "waiting_input"
            }
        else:
            return self._request_gene_input()
    
    async def _run_analysis(self, gene: str, task_id: str):
        """
        执行实际的分析流程（异步后台任务）
        保持与原有graph_runner的兼容性
        """
        try:
            # 更新任务状态（使用自己的缓存）
            self.cache_set(f"task_status_{task_id}", "running", timeout=3600)
            
            # 导入并初始化graph runner（保持兼容性）
            from agent_core.state_machine.graph_runner import GraphRunner
            
            if not self.graph_runner:
                self.graph_runner = GraphRunner(self.config)
            
            print(f"[Control Agent] 开始分析 {gene} (任务ID: {task_id})")
            
            # 调用原有的graph runner（保持兼容）
            result = await self.graph_runner.run({
                "gene_name": gene,
                "mode": "deep",
                "parallel": self.config.get("parallel", True)
            })
            
            # 生成报告文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"reports/{gene}_report_{timestamp}.html"
            
            # 保存报告文件
            import os
            os.makedirs("reports", exist_ok=True)
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(result.get("final_report", ""))
            
            # 使用自己的缓存保存结果（按月缓存）
            cache_key = f"gene_report_{gene}_{datetime.now().strftime('%Y-%m')}"
            cache_value = {
                "report_url": report_filename,
                "report_content": result.get("final_report"),
                "generated_at": datetime.now().isoformat(),
                "gene": gene
            }
            
            # 缓存30天
            self.cache_set(cache_key, cache_value, timeout=30*24*3600)
            
            # 更新任务状态
            self.cache_set(f"task_status_{task_id}", "completed", timeout=3600)
            
            print(f"[Control Agent] {gene} 分析完成，报告已保存: {report_filename}")
            
        except Exception as e:
            print(f"[Control Agent] 分析任务失败: {str(e)}")
            self.cache_set(f"task_status_{task_id}", f"error: {str(e)}", timeout=3600)
    
    # ========== 缓存管理接口方法 ==========
    def get_cached_report(self, gene: str) -> Optional[Dict]:
        """
        获取缓存的基因报告（对外接口）
        
        Args:
            gene: 基因名称
            
        Returns:
            缓存的报告数据，如果没有则返回None
        """
        cache_key = f"gene_report_{gene}_{datetime.now().strftime('%Y-%m')}"
        return self.cache_get(cache_key)
    
    def clear_gene_cache(self, gene: str) -> bool:
        """
        清除特定基因的缓存（强制刷新）
        
        Args:
            gene: 基因名称
            
        Returns:
            是否成功清除
        """
        cache_key = f"gene_report_{gene}_{datetime.now().strftime('%Y-%m')}"
        return self.cache_delete(cache_key)
    
    def get_cache_status(self) -> Dict:
        """
        获取缓存状态信息
        
        Returns:
            缓存统计信息
        """
        # 内存缓存统计
        memory_count = len(self._cache_store)
        
        # 文件缓存统计
        file_count = 0
        if os.path.exists(self._cache_dir):
            file_count = len([f for f in os.listdir(self._cache_dir) if f.endswith('.cache')])
        
        return {
            "memory_cache_count": memory_count,
            "file_cache_count": file_count,
            "cache_directory": self._cache_dir,
            "cached_genes": self._get_cached_genes()
        }
    
    def _get_cached_genes(self) -> List[str]:
        """获取所有缓存的基因列表"""
        genes = []
        for key in self._cache_store.keys():
            if key.startswith("gene_report_"):
                gene = key.split("_")[2]  # gene_report_GENENAME_YYYY-MM
                if gene not in genes:
                    genes.append(gene)
        return genes


# 便于测试的辅助函数
async def test_control_agent():
    """测试无状态的Control Agent"""
    agent = ControlAgent()
    
    # 测试场景1：初始对话
    print("\n=== 测试1：初始对话 ===")
    response = await agent.process_message(
        "我想做基因分析",
        []  # 空历史
    )
    print(response['message'])
    
    # 测试场景2：提到基因
    print("\n=== 测试2：提到基因 ===") 
    history = [
        {"role": "user", "content": "我想做基因分析"},
        {"role": "assistant", "content": "请告诉我您想分析的基因"}
    ]
    response = await agent.process_message(
        "帮我看看IL17RA",
        history
    )
    print(response['message'])
    
    # 测试场景3：确认分析
    print("\n=== 测试3：确认分析 ===")
    history.append({"role": "user", "content": "帮我看看IL17RA"})
    history.append({"role": "assistant", "content": response['message']})
    
    response = await agent.process_message(
        "确认",
        history
    )
    print(response['message'])


if __name__ == "__main__":
    asyncio.run(test_control_agent())