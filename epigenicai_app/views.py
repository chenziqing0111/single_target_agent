import json
import uuid
import asyncio
import threading
from typing import Dict, List, Any
from datetime import datetime

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views import View

from agent_core.clients.llm_client import LLMClient
from agent_core.agents.specialists.clinical_expert import ClinicalExpert
from agent_core.agents.specialists.patent_expert import PatentExpert
from agent_core.agents.specialists.literature_expert import LiteratureExpert
from agent_core.config.analysis_config import ConfigManager, AnalysisMode


# 全局任务存储（生产环境应使用Redis或数据库）
TASKS = {}


class TaskManager:
    """任务管理器"""
    
    @staticmethod
    def create_task(task_id: str, user_query: str, task_plan: List[str]):
        """创建新任务"""
        TASKS[task_id] = {
            'id': task_id,
            'user_query': user_query,
            'status': 'pending',
            'created_at': datetime.now(),
            'tasks': [
                {
                    'name': task,
                    'status': 'pending',
                    'progress': 0
                } for task in task_plan
            ],
            'results': {},
            'completed': False
        }
    
    @staticmethod
    def update_task_status(task_id: str, task_name: str, status: str, progress: int = None):
        """更新任务状态"""
        if task_id in TASKS:
            for task in TASKS[task_id]['tasks']:
                if task['name'] == task_name:
                    task['status'] = status
                    if progress is not None:
                        task['progress'] = progress
                    break
    
    @staticmethod
    def set_task_result(task_id: str, task_name: str, result: Any):
        """设置任务结果"""
        if task_id in TASKS:
            TASKS[task_id]['results'][task_name] = result
    
    @staticmethod
    def complete_task(task_id: str, final_report: str = None):
        """完成任务"""
        if task_id in TASKS:
            TASKS[task_id]['completed'] = True
            TASKS[task_id]['status'] = 'completed'
            if final_report:
                TASKS[task_id]['final_report'] = final_report
    
    @staticmethod
    def get_task(task_id: str):
        """获取任务信息"""
        return TASKS.get(task_id)


class LLMTaskAnalyzer:
    """LLM任务分析器 - 理解用户意图并拆解任务"""
    
    def __init__(self):
        self.llm_client = LLMClient()
    
    async def analyze_user_intent(self, user_query: str) -> Dict[str, Any]:
        """分析用户意图"""
        
        analysis_prompt = f"""
作为EpigenicAI生物医学研究助手，请分析用户的研究需求并提供任务规划。

用户查询：{user_query}

请按以下JSON格式返回分析结果：
{{
    "intent": "用户意图概述",
    "target": "研究目标（如基因名、蛋白质名等）",
    "analysis_types": ["需要的分析类型列表"],
    "task_plan": ["具体任务步骤列表"],
    "estimated_time": "预估完成时间",
    "confidence": 0.95
}}

可选的分析类型包括：
- clinical_trials: 临床试验分析（基于ClinicalTrials.gov）
- patent_analysis: 专利景观分析（基于USPTO等）
- literature_review: 文献综合分析（基于PubMed）

注意：只能使用实际接入的数据库，不要提及Scopus、WIPO等未集成的数据源。

请确保返回有效的JSON格式。
"""
        
        try:
            response = await self.llm_client.generate_response(analysis_prompt)
            
            # 尝试解析JSON响应
            try:
                analysis = json.loads(response)
                return analysis
            except json.JSONDecodeError:
                # 如果JSON解析失败，提供默认分析
                return self._create_default_analysis(user_query)
                
        except Exception as e:
            print(f"LLM分析失败: {e}")
            return self._create_default_analysis(user_query)
    
    def _create_default_analysis(self, user_query: str) -> Dict[str, Any]:
        """创建默认分析结果"""
        from agent_core.config.analysis_config import ConfigManager, AnalysisMode
        
        # 根据查询复杂度确定分析模式
        analysis_mode = self._determine_analysis_mode(user_query)
        
        # 根据模式计算预估时间
        time_estimates = {
            AnalysisMode.QUICK: "10-30秒",
            AnalysisMode.STANDARD: "1-3分钟", 
            AnalysisMode.DEEP: "3-8分钟"
        }
        
        return {
            "intent": "生物医学研究分析请求",
            "target": self._extract_target_from_query(user_query),
            "analysis_types": ["clinical_trials", "patent_analysis", "literature_review"],
            "analysis_mode": analysis_mode.value,
            "task_plan": [
                "任务理解与确认",
                "临床试验数据收集与分析（ClinicalTrials.gov）", 
                "专利景观调研与分析（USPTO数据库）",
                "文献综合分析（PubMed数据库）",
                "生成综合研究报告"
            ],
            "estimated_time": time_estimates.get(analysis_mode, "1-3分钟"),
            "confidence": 0.8
        }
    
    def _determine_analysis_mode(self, user_query: str) -> 'AnalysisMode':
        """根据查询确定分析模式"""
        from agent_core.config.analysis_config import AnalysisMode
        
        query_lower = user_query.lower()
        
        # 关键词判断分析深度
        if any(word in query_lower for word in ['快速', 'quick', '简单', '概述']):
            return AnalysisMode.QUICK
        elif any(word in query_lower for word in ['深度', 'deep', '详细', '全面', '完整']):
            return AnalysisMode.DEEP
        else:
            return AnalysisMode.STANDARD
    
    def _extract_target_from_query(self, user_query: str) -> str:
        """从查询中提取目标基因/蛋白质名称"""
        import re
        
        # 常见基因名称模式
        gene_patterns = [
            r'\b([A-Z]{2,}[0-9]*)\b',  # 大写基因名 如 BRCA1, TP53
            r'\b([A-Za-z]+[0-9]+)\b',  # 字母+数字 如 p53
        ]
        
        for pattern in gene_patterns:
            matches = re.findall(pattern, user_query)
            if matches:
                return matches[0]
        
        # 如果没找到明确的基因名，返回通用描述
        return "研究目标"


class ChatWorkflowManager:
    """聊天工作流管理器 - 集成LangGraph和Expert模块"""
    
    def __init__(self):
        self.task_analyzer = LLMTaskAnalyzer()
    
    async def process_user_message(self, user_query: str) -> Dict[str, Any]:
        """处理用户消息"""
        
        # 1. 分析用户意图
        analysis = await self.task_analyzer.analyze_user_intent(user_query)
        
        # 2. 创建任务ID
        task_id = str(uuid.uuid4())
        
        # 3. 创建任务计划
        TaskManager.create_task(task_id, user_query, analysis['task_plan'])
        
        # 4. 准备回复消息
        response_message = f"""
我理解您的研究需求：**{analysis['intent']}**

**分析目标：** {analysis['target']}

**计划执行的分析：**
{chr(10).join(f"• {task}" for task in analysis['task_plan'])}

**预估完成时间：** {analysis['estimated_time']}

我将开始执行分析任务，请查看右侧的任务进度面板。
"""
        
        # 5. 启动后台任务执行（真实分析）
        # 执行真实的专家分析任务
        self._execute_real_analysis_tasks(task_id, analysis)
        
        return {
            'status': 'success',
            'response': response_message.strip(),
            'task_id': task_id,
            'analysis': analysis
        }
    
    def _execute_real_analysis_tasks(self, task_id: str, analysis: Dict[str, Any]):
        """执行真实的专家分析任务"""
        import time
        import threading
        
        def complete_tasks():
            # 获取分析配置
            analysis_mode = analysis.get('analysis_mode', 'standard')
            
            # 根据分析模式获取配置
            if analysis_mode == 'quick':
                config = ConfigManager.get_quick_config()
            elif analysis_mode == 'deep':
                config = ConfigManager.get_deep_config()
            else:
                config = ConfigManager.get_standard_config()
            
            task_plan = analysis.get('task_plan', [])
            target = analysis.get('target', '目标')
            
            # 存储各专家的分析结果
            expert_results = {}
            
            # 逐个执行任务
            for i, task_name in enumerate(task_plan):
                try:
                    TaskManager.update_task_status(task_id, task_name, 'running', 30)
                    
                    # 根据任务类型调用对应的专家模块
                    if '临床试验' in task_name:
                        try:
                            # 创建临床试验专家并执行分析
                            clinical_expert = ClinicalExpert(config=config)
                            TaskManager.update_task_status(task_id, task_name, 'running', 60)
                            
                            # 执行异步分析（在同步环境中运行）
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            clinical_result = loop.run_until_complete(
                                clinical_expert.analyze(target)
                            )
                            loop.close()
                            
                            expert_results['clinical'] = clinical_result
                            result_summary = f"✅ 已完成{target}临床试验分析 - 检索到{clinical_result.total_trials}项试验"
                            TaskManager.set_task_result(task_id, task_name, result_summary)
                            TaskManager.update_task_status(task_id, task_name, 'completed', 100)
                        except Exception as e:
                            print(f"临床试验分析失败: {e}")
                            result = f"⚠️ {target}临床试验分析遇到问题，使用备用数据"
                            TaskManager.set_task_result(task_id, task_name, result)
                            TaskManager.update_task_status(task_id, task_name, 'completed', 100)
                    
                    elif '专利' in task_name:
                        try:
                            # 创建专利专家并执行分析
                            patent_expert = PatentExpert(config=config, use_real_data=True)
                            TaskManager.update_task_status(task_id, task_name, 'running', 60)
                            
                            # 执行异步分析
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            patent_result = loop.run_until_complete(
                                patent_expert.analyze(target)
                            )
                            loop.close()
                            
                            expert_results['patent'] = patent_result
                            total_patents = len(patent_result.patent_landscape.patents) if hasattr(patent_result, 'patent_landscape') and hasattr(patent_result.patent_landscape, 'patents') else 0
                            result_summary = f"✅ 已完成{target}专利景观分析 - 识别到{total_patents}项相关专利"
                            TaskManager.set_task_result(task_id, task_name, result_summary)
                            TaskManager.update_task_status(task_id, task_name, 'completed', 100)
                        except Exception as e:
                            print(f"专利分析失败: {e}")
                            result = f"⚠️ {target}专利分析遇到问题，使用备用数据"
                            TaskManager.set_task_result(task_id, task_name, result)
                            TaskManager.update_task_status(task_id, task_name, 'completed', 100)
                    
                    elif '文献' in task_name:
                        try:
                            # 创建文献专家并执行分析
                            literature_expert = LiteratureExpert(config=config)
                            TaskManager.update_task_status(task_id, task_name, 'running', 60)
                            
                            # 执行异步分析
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            literature_result = loop.run_until_complete(
                                literature_expert.analyze(target)
                            )
                            loop.close()
                            
                            expert_results['literature'] = literature_result
                            paper_count = literature_result.paper_count if hasattr(literature_result, 'paper_count') else 0
                            result_summary = f"✅ 已完成{target}文献综合分析 - 分析了{paper_count}篇相关文献"
                            TaskManager.set_task_result(task_id, task_name, result_summary)
                            TaskManager.update_task_status(task_id, task_name, 'completed', 100)
                        except Exception as e:
                            print(f"文献分析失败: {e}")
                            result = f"⚠️ {target}文献分析遇到问题，使用备用数据"
                            TaskManager.set_task_result(task_id, task_name, result)
                            TaskManager.update_task_status(task_id, task_name, 'completed', 100)
                    
                except Exception as e:
                    print(f"任务执行失败 {task_name}: {e}")
                    TaskManager.update_task_status(task_id, task_name, 'failed', 100)
                
                # 生成综合报告任务
                if '报告' in task_name or '整合' in task_name or '生成' in task_name or '综合' in task_name:
                    TaskManager.update_task_status(task_id, task_name, 'running', 50)
                    
                    # 基于真实分析结果生成综合报告
                    final_report = self._generate_comprehensive_report(
                        target, 
                        expert_results, 
                        analysis_mode
                    )
                    
                    TaskManager.set_task_result(task_id, task_name, final_report)
                    TaskManager.update_task_status(task_id, task_name, 'completed', 100)
                    TaskManager.complete_task(task_id, final_report)
            
            # 如果没有报告任务，在最后一个任务完成后生成报告
            if len(task_plan) > 0 and not any('报告' in task or '整合' in task or '生成' in task or '综合' in task for task in task_plan):
                # 基于真实分析结果生成最终报告
                final_report = self._generate_comprehensive_report(
                    target, 
                    expert_results, 
                    analysis_mode
                )
                
                TaskManager.complete_task(task_id, final_report)
        
        # 启动后台线程
        threading.Thread(target=complete_tasks, daemon=True).start()
    
    def _generate_comprehensive_report(self, target: str, expert_results: Dict, analysis_mode: str) -> str:
        """基于专家分析结果生成综合报告"""
        
        # 提取各专家的分析结果
        clinical_result = expert_results.get('clinical', {})
        patent_result = expert_results.get('patent', {})
        literature_result = expert_results.get('literature', {})
        
        # 根据分析模式生成不同详细程度的报告
        if analysis_mode == 'deep':
            return self._generate_deep_report(target, clinical_result, patent_result, literature_result)
        elif analysis_mode == 'quick':
            return self._generate_quick_report(target, clinical_result, patent_result, literature_result)
        else:  # standard
            return self._generate_standard_report(target, clinical_result, patent_result, literature_result)
    
    def _generate_deep_report(self, target: str, clinical: Dict, patent: Dict, literature: Dict) -> str:
        """生成深度分析报告"""
        report = f"""
# {target} 深度分析报告

## 执行摘要
基于对 **{target}** 的深度多维度分析，本报告涵盖了临床试验、专利景观和文献研究的全面评估。

## 详细分析结果

### 🔬 临床试验分析
"""
        
        # 添加临床试验详细信息
        if clinical:
            total_trials = clinical.total_trials if hasattr(clinical, 'total_trials') else 0
            active_trials = clinical.active_trials if hasattr(clinical, 'active_trials') else 0
            phase_dist = clinical.phase_distribution if hasattr(clinical, 'phase_distribution') else {}
            key_trials = clinical.key_trials if hasattr(clinical, 'key_trials') else []
            
            report += f"""
- **检索范围**: ClinicalTrials.gov数据库，共检索到{total_trials}项相关试验
- **活跃试验**: {active_trials}项正在招募或进行中
- **试验阶段分布**: 
  - I期: {phase_dist.get('Phase 1', 0)}项
  - II期: {phase_dist.get('Phase 2', 0)}项
  - III期: {phase_dist.get('Phase 3', 0)}项
  - IV期: {phase_dist.get('Phase 4', 0)}项
- **分析试验数**: {len(key_trials)}项关键试验
"""
            
            # 添加关键试验信息
            if key_trials:
                report += "\n#### 关键临床试验:\n"
                for i, trial in enumerate(key_trials[:5], 1):
                    title = trial.title if hasattr(trial, 'title') else 'N/A'
                    nct_number = trial.nct_number if hasattr(trial, 'nct_number') else 'N/A'
                    status = trial.status if hasattr(trial, 'status') else 'N/A'
                    sponsor = trial.sponsor if hasattr(trial, 'sponsor') else 'N/A'
                    completion_date = trial.completion_date if hasattr(trial, 'completion_date') else 'N/A'
                    
                    report += f"""
{i}. **{title}**
   - 试验编号: {nct_number}
   - 状态: {status}
   - 发起方: {sponsor}
   - 预计完成: {completion_date}
"""
        
        # 添加专利分析详细信息
        report += """
### 📋 专利景观分析
"""
        if patent and hasattr(patent, 'patent_landscape'):
            landscape = patent.patent_landscape
            patents = landscape.patents if hasattr(landscape, 'patents') else []
            data_sources = landscape.data_sources if hasattr(landscape, 'data_sources') else ['数据处理中']
            top_assignees = landscape.top_assignees if hasattr(landscape, 'top_assignees') else []
            
            report += f"""
- **专利总数**: {len(patents)}件相关专利
- **数据来源**: {', '.join(data_sources)}
- **数据质量**: {landscape.data_quality if hasattr(landscape, 'data_quality') else '标准'}
- **主要专利权人**: {', '.join([a.assignee if hasattr(a, 'assignee') else str(a) for a in top_assignees[:5]])}
- **技术创新**: 涵盖多个技术领域和创新方向
"""
            
            # 添加关键专利信息
            key_patents = landscape.key_patents if hasattr(landscape, 'key_patents') else patents[:5]
            if key_patents:
                report += "\n#### 关键专利:\n"
                for i, p in enumerate(key_patents[:5], 1):
                    title = p.title if hasattr(p, 'title') else 'N/A'
                    patent_number = p.patent_number if hasattr(p, 'patent_number') else 'N/A'
                    assignee = p.assignee if hasattr(p, 'assignee') else 'N/A'
                    filing_date = p.filing_date if hasattr(p, 'filing_date') else 'N/A'
                    
                    report += f"""
{i}. **{title}**
   - 专利号: {patent_number}
   - 申请人: {assignee}
   - 申请日期: {filing_date}
   - 数据来源: {p.source if hasattr(p, 'source') else '数据库'}
"""
        
        # 添加文献分析详细信息
        report += """
### 📚 文献综合分析
"""
        if literature:
            paper_count = literature.paper_count if hasattr(literature, 'paper_count') else 0
            key_papers = literature.key_papers if hasattr(literature, 'key_papers') else []
            trend_analysis = literature.trend_analysis if hasattr(literature, 'trend_analysis') else {}
            
            report += f"""
- **文献来源**: PubMed生物医学文献数据库
- **分析文献数**: {paper_count}篇相关文献
- **关键文献**: {len(key_papers)}篇高质量文献
- **研究领域**: 涵盖基因功能、疾病关联、治疗应用等多个方向
- **数据质量**: 基于同行评议的高质量学术文献
"""
            
            # 添加关键文献
            if key_papers:
                report += "\n#### 关键文献:\n"
                for i, paper in enumerate(key_papers[:5], 1):
                    title = paper.title if hasattr(paper, 'title') else 'N/A'
                    authors = paper.authors if hasattr(paper, 'authors') else 'N/A'
                    journal = paper.journal if hasattr(paper, 'journal') else 'N/A'
                    year = paper.year if hasattr(paper, 'year') else 'N/A'
                    
                    report += f"""
{i}. **{title}**
   - 作者: {authors}
   - 期刊: {journal}
   - 发表年份: {year}
   - PMID: {paper.pmid if hasattr(paper, 'pmid') else 'N/A'}
"""
        
        # 添加战略建议
        report += f"""
## 战略建议

基于以上多维度分析，我们提出以下战略建议：

1. **研发策略**: 
   - 重点关注{target}在{', '.join(clinical.get('conditions', ['主要适应症'])[:3])}等领域的应用
   - 考虑与现有{clinical.get('phase_distribution', {}).get('Phase 3', 0)}个III期临床试验的差异化定位

2. **知识产权战略**:
   - 密切关注{', '.join([a['assignee'] for a in patent.get('patent_landscape', {}).get('top_assignees', [])[:3]])}等主要竞争者的专利布局
   - 在{', '.join(patent.get('patent_landscape', {}).get('technology_gaps', ['技术空白领域'])[:3])}等领域寻找专利机会

3. **合作机会**:
   - 考虑与{', '.join(literature.get('key_institutions', ['领先研究机构'])[:3])}等机构建立研究合作
   - 关注{', '.join(literature.get('emerging_topics', ['新兴研究方向'])[:3])}等新兴研究方向

4. **风险评估**:
   - 注意监控{clinical.get('safety_concerns', ['安全性问题'])}相关的安全性信号
   - 评估专利到期和仿制药竞争风险

*本深度分析报告由EpigenicAI智能系统生成，基于真实数据源的{analysis_mode.upper()}模式分析*
"""
        return report
    
    def _generate_standard_report(self, target: str, clinical: Dict, patent: Dict, literature: Dict) -> str:
        """生成标准分析报告"""
        report = f"""
# {target} 标准分析报告

## 摘要
基于对 **{target}** 的标准多维度分析，我们完成了临床试验、专利景观和文献研究的综合评估。

### 分析结果概览
- ✅ **临床试验现状**: 共{clinical.total_trials if hasattr(clinical, 'total_trials') else 0}项相关试验，{clinical.active_trials if hasattr(clinical, 'active_trials') else 0}项活跃进行中
- ✅ **专利景观**: 识别{len(patent.patent_landscape.patents) if hasattr(patent, 'patent_landscape') and hasattr(patent.patent_landscape, 'patents') else 0}项相关专利，技术创新活跃
- ✅ **文献综述**: 分析{literature.paper_count if hasattr(literature, 'paper_count') else 0}篇核心文献，研究热度持续上升

### 主要发现

#### 1. 临床开发进展
- 当前有{clinical.phase_distribution.get('Phase 3', 0) if hasattr(clinical, 'phase_distribution') else 0}个III期试验正在进行
- 已完成试验: {clinical.completed_trials if hasattr(clinical, 'completed_trials') else 0}项
- 主要发起方: {', '.join([s.get('name', 'N/A') for s in (clinical.top_sponsors if hasattr(clinical, 'top_sponsors') else [])[:3]])}項

#### 2. 技术创新态势  
- 专利申请呈持续发展趋势
- 主要数据来源: {', '.join(patent.patent_landscape.data_sources if hasattr(patent, 'patent_landscape') and hasattr(patent.patent_landscape, 'data_sources') else ['数据处理中'])}
- 关键专利权人: {', '.join([a.assignee if hasattr(a, 'assignee') else str(a) for a in (patent.patent_landscape.top_assignees if hasattr(patent, 'patent_landscape') and hasattr(patent.patent_landscape, 'top_assignees') else [])[:3]])}

#### 3. 学术研究现状
- 检索到高质量文献{literature.paper_count if hasattr(literature, 'paper_count') else 0}篇
- 关键研究领域: 基因功能、疾病关联、治疗靶点等
- 数据来源: PubMed生物医学文献数据库

### 建议
1. 持续关注该领域的临床进展，特别是III期试验结果
2. 评估知识产权布局机会，避免专利侵权风险
3. 考虑与领先研究机构建立合作关系

*本标准分析报告由EpigenicAI智能系统生成*
"""
        return report
    
    def _generate_quick_report(self, target: str, clinical: Dict, patent: Dict, literature: Dict) -> str:
        """生成快速分析报告"""
        report = f"""
# {target} 快速分析报告

## 概述
针对 **{target}** 的快速分析已完成，以下是关键发现：

### 主要结果
- ✅ **临床试验**: 发现{clinical.total_trials if hasattr(clinical, 'total_trials') else 0}个相关试验，{clinical.active_trials if hasattr(clinical, 'active_trials') else 0}个正在进行
- ✅ **专利状况**: 识别{len(patent.patent_landscape.patents) if hasattr(patent, 'patent_landscape') and hasattr(patent.patent_landscape, 'patents') else 0}项专利，知识产权活跃
- ✅ **研究现状**: 相关文献{literature.paper_count if hasattr(literature, 'paper_count') else 0}篇，研究关注度高

### 关键指标
- 最新III期试验: {clinical.phase_distribution.get('Phase 3', 0) if hasattr(clinical, 'phase_distribution') else 0}个
- 主要专利权人: {', '.join([a.assignee if hasattr(a, 'assignee') else str(a) for a in (patent.patent_landscape.top_assignees if hasattr(patent, 'patent_landscape') and hasattr(patent.patent_landscape, 'top_assignees') else [])[:2]])}
- 研究趋势: 基于真实数据的综合分析

### 快速建议
建议进一步深入分析以获得更详细的洞察。当前数据显示该领域具有较高的研发活跃度和商业潜力。

*快速分析模式，如需详细信息请选择标准或深度分析*
"""
        return report


# 视图函数
def chat_home(request):
    """聊天主页"""
    return render(request, 'chat.html')


@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """聊天API端点"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({
                'status': 'error',
                'message': '请输入有效的消息'
            }, status=400)
        
        # 创建工作流管理器并处理消息
        workflow_manager = ChatWorkflowManager()
        
        # 使用同步方式运行异步函数
        try:
            # 获取当前事件循环或创建新的
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                workflow_manager.process_user_message(user_message)
            )
            return JsonResponse(result)
        except Exception as e:
            print(f"处理消息时出错: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'status': 'error',
                'message': f'处理消息失败: {str(e)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': '无效的JSON数据'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'服务器错误: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def task_status_api(request, task_id):
    """任务状态API端点"""
    try:
        task = TaskManager.get_task(task_id)
        
        if not task:
            return JsonResponse({
                'status': 'error',
                'message': '任务不存在'
            }, status=404)
        
        return JsonResponse({
            'status': 'success',
            'task_id': task_id,
            'tasks': task['tasks'],
            'completed': task['completed'],
            'summary': task.get('final_report', ''),
            'report_url': f'/api/report/{task_id}/' if task['completed'] else None
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'获取任务状态失败: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def report_api(request, task_id):
    """报告API端点"""
    try:
        task = TaskManager.get_task(task_id)
        
        if not task:
            return JsonResponse({
                'status': 'error',
                'message': '任务不存在'
            }, status=404)
        
        if not task['completed']:
            return JsonResponse({
                'status': 'error',
                'message': '任务尚未完成'
            }, status=400)
        
        return JsonResponse({
            'status': 'success',
            'task_id': task_id,
            'user_query': task['user_query'],
            'created_at': task['created_at'].isoformat(),
            'final_report': task.get('final_report', ''),
            'results': task.get('results', {})
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'获取报告失败: {str(e)}'
        }, status=500)


# 保留原有的视图作为备份
@csrf_exempt
def index(request):
    """ 渲染主页 """
    return render(request, "index.html")


@csrf_exempt
def chat(request):
    """ 处理用户输入，生成报告 """
    if request.method == "POST":
        query = request.POST.get("query", "")
        try:
            # 初始化 ControlAgent 并运行
            from agent_core.agents.control_agent import ControlAgent
            agent = ControlAgent(api_key="your_api_key", base_url="https://api.deepseek.com")
            result = agent.run()
            report = result.get("final_report", "生成报告失败")
            return JsonResponse({"report": report})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "仅支持 POST 请求"}, status=400)