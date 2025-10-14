# agent_core/agents/specialists/clinical_expert.py (配置版)

import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

# 导入配置系统
from agent_core.config.analysis_config import (
    AnalysisConfig, AnalysisMode, ConfigManager
)

logger = logging.getLogger(__name__)

@dataclass
class ClinicalTrial:
    """临床试验数据结构"""
    nct_id: str
    title: str
    status: str
    phase: str
    sponsor: str
    condition: str
    intervention: str
    enrollment: int
    start_date: Optional[str]
    completion_date: Optional[str]
    primary_outcome: str
    study_design: str
    locations: List[str]
    url: str
    brief_summary: Optional[str] = ""
    detailed_description: Optional[str] = ""

@dataclass
class ClinicalAnalysisResult:
    """临床分析结果"""
    gene_target: str
    total_trials: int
    active_trials: int
    completed_trials: int
    analyzed_trials: int  # 新增：实际分析的试验数
    
    # 按阶段分布
    phase_distribution: Dict[str, int]
    
    # 按状态分布
    status_distribution: Dict[str, int]
    
    # 按适应症分布
    indication_distribution: Dict[str, int]
    
    # 主要发起方
    top_sponsors: List[Dict[str, Any]]
    
    # 关键试验详情
    key_trials: List[ClinicalTrial]
    
    # 发展趋势
    temporal_trends: Dict[str, Any]
    
    # 分析总结
    summary: str
    confidence_score: float
    last_updated: str
    
    # 配置和使用情况
    config_used: Dict[str, Any]
    token_usage: Dict[str, int]

class ClinicalExpert:
    """临床专家Agent - 支持配置化分析"""
    
    def __init__(self, config: AnalysisConfig = None):
        self.name = "Clinical Expert"
        self.version = "2.0.0"
        self.expertise = [
            "clinical_trials_analysis",
            "drug_development_pipeline", 
            "regulatory_landscape",
            "clinical_outcomes_assessment"
        ]
        
        # 使用配置
        self.config = config or ConfigManager.get_standard_config()
        
        # 延迟导入，避免循环依赖
        self._retriever = None
        self._analyzer = None
        
        logger.info(f"初始化 {self.name} - 模式: {self.config.mode.value}")
        
    @property
    def retriever(self):
        """延迟初始化retriever"""
        if self._retriever is None:
            from agent_core.agents.workers.knowledge_retriever import KnowledgeRetriever
            self._retriever = KnowledgeRetriever()
        return self._retriever
    
    @property 
    def analyzer(self):
        """延迟初始化analyzer"""
        if self._analyzer is None:
            from agent_core.agents.workers.data_analyzer import DataAnalyzer
            self._analyzer = DataAnalyzer()
        return self._analyzer
    
    def set_config(self, config: AnalysisConfig):
        """动态设置配置"""
        self.config = config
        logger.info(f"配置已更新为: {config.mode.value}")
    
    def set_mode(self, mode: AnalysisMode):
        """快速设置分析模式"""
        self.config = ConfigManager.get_config_by_mode(mode)
        logger.info(f"模式已切换为: {mode.value}")
    
    async def analyze(self, gene_target: str, context: Dict[str, Any] = None) -> ClinicalAnalysisResult:
        """
        主要分析入口：分析特定基因/靶点的临床试验进展
        
        Args:
            gene_target: 目标基因名称（如 "PCSK9", "EGFR"）
            context: 额外上下文信息，会覆盖配置中的设置
        
        Returns:
            ClinicalAnalysisResult: 临床分析结果
        """
        logger.info(f"开始分析 {gene_target} - 模式: {self.config.mode.value}")
        
        # 估算Token使用量
        token_estimate = ConfigManager.estimate_token_usage(self.config)
        logger.info(f"预估Token使用: {token_estimate['total_tokens']}")
        
        try:
            # 1. 检索临床试验数据（受配置控制）
            trials_data = await self._retrieve_clinical_data(gene_target, context)
            
            # 2. 解析和清洗数据（受配置控制）
            parsed_trials = self._parse_trials_data(trials_data)
            
            # 3. 根据配置限制分析数量
            trials_to_analyze = self._limit_trials_for_analysis(parsed_trials)
            
            # 4. 深度分析（受配置控制）
            analysis_result = await self._perform_analysis(gene_target, trials_to_analyze, context)
            
            # 5. 添加配置和使用情况信息
            analysis_result.config_used = self._get_config_summary()
            analysis_result.token_usage = token_estimate
            analysis_result.analyzed_trials = len(trials_to_analyze)
            
            logger.info(f"完成 {gene_target} 分析 - 检索: {len(parsed_trials)}, 分析: {len(trials_to_analyze)}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"分析 {gene_target} 时发生错误: {str(e)}")
            return self._create_error_result(gene_target, str(e))
    
    async def _retrieve_clinical_data(self, gene_target: str, context: Dict = None) -> Dict[str, Any]:
        """检索临床试验数据（配置化）"""
        
        # 合并配置和上下文参数
        ct_config = self.config.clinical_trials
        
        query_params = {
            "gene": gene_target,
            "page_size": ct_config.page_size,
            "max_pages": ct_config.max_pages,
            "sources": ["clinicaltrials_gov"],
        }
        
        # 上下文参数覆盖配置
        if context:
            query_params.update({k: v for k, v in context.items() 
                               if k in ["condition", "phase", "sponsor", "page_size", "max_pages"]})
        
        logger.info(f"检索参数: page_size={query_params['page_size']}, max_pages={query_params['max_pages']}")
        
        # 调用retriever
        trials_data = await self.retriever.retrieve_clinical_trials(query_params)
        
        return trials_data
    
    def _limit_trials_for_analysis(self, parsed_trials: List[ClinicalTrial]) -> List[ClinicalTrial]:
        """根据配置限制要分析的试验数量"""
        
        max_analyze = self.config.clinical_trials.max_trials_analyze
        
        if len(parsed_trials) <= max_analyze:
            return parsed_trials
        
        # 按重要性排序，取前N个
        scored_trials = []
        for trial in parsed_trials:
            score = self._calculate_trial_importance_score(trial)
            scored_trials.append((trial, score))
        
        # 按评分排序
        scored_trials.sort(key=lambda x: x[1], reverse=True)
        
        # 取前max_analyze个
        selected_trials = [trial for trial, score in scored_trials[:max_analyze]]
        
        logger.info(f"从 {len(parsed_trials)} 个试验中选择 {len(selected_trials)} 个进行分析")
        
        return selected_trials
    
    def _calculate_trial_importance_score(self, trial: ClinicalTrial) -> float:
        """计算试验重要性评分"""
        score = 0.0
        
        # 阶段评分
        if "III" in trial.phase:
            score += 3.0
        elif "II" in trial.phase:
            score += 2.0
        elif "I" in trial.phase:
            score += 1.0
        
        # 状态评分
        if trial.status in ["Recruiting", "Active, not recruiting"]:
            score += 1.0
        elif trial.status == "Completed":
            score += 0.5
        
        # 规模评分
        if trial.enrollment > 500:
            score += 1.0
        elif trial.enrollment > 100:
            score += 0.5
        
        # 信息完整性评分
        if trial.brief_summary and len(trial.brief_summary) > 100:
            score += 0.5
        
        if trial.detailed_description and len(trial.detailed_description) > 200:
            score += 0.5
        
        return score
    
    def _parse_trials_data(self, trials_data: Dict[str, Any]) -> List[ClinicalTrial]:
        """解析临床试验数据（配置化）"""
        parsed_trials = []
        
        raw_trials = trials_data.get("trials", [])
        fields_to_analyze = self.config.clinical_trials.fields_to_analyze
        use_detailed = self.config.clinical_trials.use_detailed_description
        
        for trial_data in raw_trials:
            try:
                # 基础字段
                trial = ClinicalTrial(
                    nct_id=trial_data.get("nct_id", ""),
                    title=trial_data.get("title", ""),
                    status=trial_data.get("status", "Unknown"),
                    phase=self._normalize_phase(trial_data.get("phase", "")),
                    sponsor=trial_data.get("lead_sponsor", ""),
                    condition=trial_data.get("condition", ""),
                    intervention=self._extract_intervention(trial_data.get("interventions", [])),
                    enrollment=self._extract_enrollment_count(trial_data.get("enrollment", {})),
                    start_date=trial_data.get("start_date", ""),
                    completion_date=trial_data.get("completion_date", ""),
                    primary_outcome=self._extract_primary_outcome(trial_data.get("outcomes", [])),
                    study_design=trial_data.get("study_design", ""),
                    locations=self._extract_locations(trial_data.get("locations", [])),
                    url=f"https://clinicaltrials.gov/study/{trial_data.get('nct_id', '')}"
                )
                
                # 可选字段（根据配置）
                if "brief_summary" in fields_to_analyze:
                    trial.brief_summary = trial_data.get("brief_summary", "")
                
                if use_detailed and "detailed_description" in fields_to_analyze:
                    trial.detailed_description = trial_data.get("detailed_description", "")
                
                parsed_trials.append(trial)
                
            except Exception as e:
                logger.warning(f"解析试验数据时出错: {str(e)}")
                continue
        
        return parsed_trials
    
    async def _perform_analysis(self, gene_target: str, trials: List[ClinicalTrial], context: Dict = None) -> ClinicalAnalysisResult:
        """执行深度分析（配置化）"""
        
        # 根据配置决定分析的深度和内容
        analysis_sections = self.config.analysis_depth.analysis_sections
        
        # 执行多个分析任务
        phase_dist = self._analyze_phase_distribution(trials)
        status_dist = self._analyze_status_distribution(trials)
        indication_dist = self._analyze_indication_distribution(trials)
        top_sponsors = self._analyze_sponsors(trials)
        key_trials = self._identify_key_trials(trials)
        temporal_trends = self._analyze_temporal_trends(trials)
        
        # 生成分析总结（根据配置）
        summary = await self._generate_summary(gene_target, trials, {
            "phase_distribution": phase_dist,
            "status_distribution": status_dist,
            "indication_distribution": indication_dist,
            "temporal_trends": temporal_trends
        })
        
        # 计算置信度
        confidence = self._calculate_confidence_score(trials)
        
        return ClinicalAnalysisResult(
            gene_target=gene_target,
            total_trials=len(trials),
            active_trials=len([t for t in trials if t.status in ["Recruiting", "Active, not recruiting", "Enrolling by invitation"]]),
            completed_trials=len([t for t in trials if t.status == "Completed"]),
            analyzed_trials=len(trials),
            phase_distribution=phase_dist,
            status_distribution=status_dist,
            indication_distribution=indication_dist,
            top_sponsors=top_sponsors,
            key_trials=key_trials,
            temporal_trends=temporal_trends,
            summary=summary,
            confidence_score=confidence,
            last_updated=datetime.now().isoformat(),
            config_used={},  # 稍后填充
            token_usage={}   # 稍后填充
        )
    
    async def _generate_summary(self, gene_target: str, trials: List[ClinicalTrial], analysis_data: Dict) -> str:
        """生成分析总结（配置化）"""
        
        total_trials = len(trials)
        if total_trials == 0:
            return f"未找到与 {gene_target} 相关的临床试验。"
        
        # 根据配置决定总结的详细程度
        include_citations = self.config.analysis_depth.include_citations
        generate_summary = self.config.analysis_depth.generate_summary
        
        if not generate_summary:
            return f"找到 {total_trials} 个与 {gene_target} 相关的临床试验。"
        
        # 基本统计
        active_count = len([t for t in trials if t.status in ["Recruiting", "Active, not recruiting"]])
        phase_dist = analysis_data["phase_distribution"]
        
        # 主要阶段
        main_phase = max(phase_dist.items(), key=lambda x: x[1])[0] if phase_dist else "Unknown"
        
        # 主要适应症
        indication_dist = analysis_data["indication_distribution"]
        main_indication = max(indication_dist.items(), key=lambda x: x[1])[0] if indication_dist else "Unknown"
        
        # 根据模式生成不同详细程度的总结
        if self.config.mode == AnalysisMode.QUICK:
            summary = f"""
{gene_target} 临床试验快速分析：

📊 基本统计: {total_trials} 个试验，{active_count} 个正在进行
🔬 主要阶段: {main_phase} ({phase_dist.get(main_phase, 0)} 个)
🎯 主要适应症: {main_indication}
""".strip()
        
        elif self.config.mode == AnalysisMode.STANDARD:
            summary = f"""
{gene_target} 临床试验标准分析：

📊 **基本统计**
- 总试验数：{total_trials} 个
- 正在进行：{active_count} 个
- 主要阶段：{main_phase} ({phase_dist.get(main_phase, 0)} 个试验)
- 主要适应症：{main_indication} ({indication_dist.get(main_indication, 0)} 个试验)

🔬 **研发热点**
{self._format_top_items(indication_dist, "适应症", max_items=3)}

📈 **发展趋势**
{self._format_trend_summary(analysis_data["temporal_trends"])}
""".strip()
        
        else:  # DEEP mode
            summary = f"""
{gene_target} 临床试验深度分析：

📊 **基本统计**
- 总试验数：{total_trials} 个
- 正在进行：{active_count} 个
- 已完成：{len([t for t in trials if t.status == "Completed"])} 个
- 主要阶段：{main_phase} ({phase_dist.get(main_phase, 0)} 个试验)
- 主要适应症：{main_indication} ({indication_dist.get(main_indication, 0)} 个试验)

🔬 **研发热点**
{self._format_top_items(indication_dist, "适应症", max_items=5)}

🏢 **主要参与方**
{self._format_sponsor_summary(analysis_data.get("top_sponsors", []), max_items=3)}

📈 **发展趋势**
{self._format_trend_summary(analysis_data["temporal_trends"])}

💡 **关键洞察**
{self._generate_insights(gene_target, trials, analysis_data)}
""".strip()
        
        return summary
    
    def _get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "mode": self.config.mode.value,
            "clinical_trials": {
                "page_size": self.config.clinical_trials.page_size,
                "max_pages": self.config.clinical_trials.max_pages,
                "max_analyze": self.config.clinical_trials.max_trials_analyze,
                "use_detailed": self.config.clinical_trials.use_detailed_description
            },
            "analysis_sections": self.config.analysis_depth.analysis_sections,
            "token_limits": {
                "max_input": self.config.tokens.max_input_tokens,
                "max_output": self.config.tokens.max_output_tokens
            }
        }
    
    # 保持原有的辅助方法
    def _normalize_phase(self, phase: str) -> str:
        """标准化试验阶段"""
        if not phase:
            return "Unknown"
        
        phase = phase.upper()
        if "I" in phase and "II" in phase and "III" in phase:
            return "Phase I/II/III"
        elif "I" in phase and "II" in phase:
            return "Phase I/II"
        elif "II" in phase and "III" in phase:
            return "Phase II/III"
        elif "III" in phase:
            return "Phase III"
        elif "II" in phase:
            return "Phase II"
        elif "I" in phase:
            return "Phase I"
        elif "IV" in phase:
            return "Phase IV"
        else:
            return "Unknown"
    
    def _extract_intervention(self, interventions: List[Dict]) -> str:
        """提取干预措施"""
        if not interventions:
            return "Unknown"
        
        intervention_names = []
        for intervention in interventions[:3]:  # 只取前3个
            name = intervention.get("name", "")
            if name:
                intervention_names.append(name)
        
        return "; ".join(intervention_names) if intervention_names else "Unknown"
    
    def _extract_enrollment_count(self, enrollment: Dict) -> int:
        """提取入组人数"""
        if isinstance(enrollment, dict):
            return enrollment.get("count", 0)
        try:
            return int(enrollment)
        except (ValueError, TypeError):
            return 0
    
    def _extract_primary_outcome(self, outcomes: List[Dict]) -> str:
        """提取主要终点"""
        for outcome in outcomes:
            if outcome.get("type") == "Primary":
                return outcome.get("measure", "Unknown")
        
        return outcomes[0].get("measure", "Unknown") if outcomes else "Unknown"
    
    def _extract_locations(self, locations: List[str]) -> List[str]:
        """提取试验地点"""
        if isinstance(locations, list):
            return locations[:5]  # 只取前5个
        return []
    
    # 其他分析方法保持不变...
    def _analyze_phase_distribution(self, trials: List[ClinicalTrial]) -> Dict[str, int]:
        """分析试验阶段分布"""
        phase_count = {}
        for trial in trials:
            phase = trial.phase or "Unknown"
            phase_count[phase] = phase_count.get(phase, 0) + 1
        return phase_count
    
    def _analyze_status_distribution(self, trials: List[ClinicalTrial]) -> Dict[str, int]:
        """分析试验状态分布"""
        status_count = {}
        for trial in trials:
            status = trial.status or "Unknown"
            status_count[status] = status_count.get(status, 0) + 1
        return status_count
    
    def _analyze_indication_distribution(self, trials: List[ClinicalTrial]) -> Dict[str, int]:
        """分析适应症分布"""
        indication_count = {}
        for trial in trials:
            condition = trial.condition or "Unknown"
            # 简化适应症名称
            simplified_condition = self._simplify_condition_name(condition)
            indication_count[simplified_condition] = indication_count.get(simplified_condition, 0) + 1
        
        # 返回前10个最常见的适应症
        sorted_indications = sorted(indication_count.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_indications[:10])
    
    def _analyze_sponsors(self, trials: List[ClinicalTrial]) -> List[Dict[str, Any]]:
        """分析主要发起方"""
        sponsor_count = {}
        
        for trial in trials:
            sponsor = trial.sponsor or "Unknown"
            sponsor_count[sponsor] = sponsor_count.get(sponsor, 0) + 1
        
        # 构建top sponsors列表
        top_sponsors = []
        for sponsor, count in sorted(sponsor_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            top_sponsors.append({
                "name": sponsor,
                "trial_count": count,
                "percentage": round(count / len(trials) * 100, 1)
            })
        
        return top_sponsors
    
    def _identify_key_trials(self, trials: List[ClinicalTrial], max_trials: int = 10) -> List[ClinicalTrial]:
        """识别关键试验"""
        
        scored_trials = []
        
        for trial in trials:
            score = self._calculate_trial_importance_score(trial)
            scored_trials.append((trial, score))
        
        # 按评分排序，返回前N个
        scored_trials.sort(key=lambda x: x[1], reverse=True)
        return [trial for trial, score in scored_trials[:max_trials]]
    
    def _analyze_temporal_trends(self, trials: List[ClinicalTrial]) -> Dict[str, Any]:
        """分析时间趋势"""
        yearly_starts = {}
        
        for trial in trials:
            if trial.start_date:
                try:
                    year = trial.start_date[:4]  # 假设格式为YYYY-MM-DD
                    if year.isdigit():
                        yearly_starts[year] = yearly_starts.get(year, 0) + 1
                except:
                    pass
        
        return {
            "yearly_trial_starts": yearly_starts,
            "trend_analysis": self._analyze_trend_direction(yearly_starts)
        }
    
    def _analyze_trend_direction(self, yearly_data: Dict[str, int]) -> str:
        """分析趋势方向"""
        if len(yearly_data) < 2:
            return "数据不足"
        
        years = sorted(yearly_data.keys())
        recent_years = years[-3:]  # 最近3年
        
        if len(recent_years) >= 2:
            recent_counts = [yearly_data[year] for year in recent_years]
            if recent_counts[-1] > recent_counts[0]:
                return "上升趋势"
            elif recent_counts[-1] < recent_counts[0]:
                return "下降趋势"
            else:
                return "稳定趋势"
        
        return "趋势不明确"
    
    def _simplify_condition_name(self, condition: str) -> str:
        """简化适应症名称"""
        if not condition:
            return "Unknown"
        
        condition = condition.lower()
        if "cancer" in condition or "carcinoma" in condition or "tumor" in condition:
            return "Cancer"
        elif "diabetes" in condition:
            return "Diabetes"
        elif "cardiovascular" in condition or "heart" in condition:
            return "Cardiovascular Disease"
        elif "alzheimer" in condition:
            return "Alzheimer's Disease"
        else:
            return condition.title()[:50]  # 限制长度
    
    def _format_top_items(self, distribution: Dict[str, int], category: str, max_items: int = 3) -> str:
        """格式化前几项"""
        if not distribution:
            return f"无{category}数据"
        
        items = []
        for item, count in list(distribution.items())[:max_items]:
            items.append(f"- {item}: {count} 个试验")
        
        return "\n".join(items)
    
    def _format_sponsor_summary(self, sponsors: List[Dict], max_items: int = 3) -> str:
        """格式化发起方总结"""
        if not sponsors:
            return "无发起方数据"
        
        items = []
        for sponsor in sponsors[:max_items]:
            name = sponsor["name"]
            count = sponsor["trial_count"]
            items.append(f"- {name}: {count} 个试验")
        
        return "\n".join(items)
    
    def _format_trend_summary(self, trends: Dict[str, Any]) -> str:
        """格式化趋势总结"""
        trend_direction = trends.get("trend_analysis", "Unknown")
        return f"近年来试验启动呈现 {trend_direction}"
    
    def _generate_insights(self, gene_target: str, trials: List[ClinicalTrial], analysis_data: Dict) -> str:
        """生成关键洞察"""
        insights = []
        
        # 基于试验数量的洞察
        total_trials = len(trials)
        if total_trials > 50:
            insights.append(f"{gene_target} 是一个研发热点靶点")
        elif total_trials > 20:
            insights.append(f"{gene_target} 受到中等程度关注")
        else:
            insights.append(f"{gene_target} 是一个新兴或小众靶点")
        
        # 基于阶段分布的洞察
        phase_dist = analysis_data["phase_distribution"]
        if phase_dist.get("Phase III", 0) > 0:
            insights.append("已有III期试验，技术相对成熟")
        elif phase_dist.get("Phase II", 0) > phase_dist.get("Phase I", 0):
            insights.append("主要处于II期验证阶段")
        
        return "; ".join(insights)
    
    def _calculate_confidence_score(self, trials: List[ClinicalTrial]) -> float:
        """计算分析置信度"""
        if not trials:
            return 0.0
        
        score = 0.5  # 基础分
        
        # 基于试验数量
        if len(trials) >= 20:
            score += 0.3
        elif len(trials) >= 10:
            score += 0.2
        elif len(trials) >= 5:
            score += 0.1
        
        # 基于数据完整性
        complete_trials = sum(1 for t in trials if t.phase and t.status and t.sponsor)
        completeness_ratio = complete_trials / len(trials)
        score += completeness_ratio * 0.2
        
        return min(score, 1.0)
    
    def _create_error_result(self, gene_target: str, error_msg: str) -> ClinicalAnalysisResult:
        """创建错误结果"""
        return ClinicalAnalysisResult(
            gene_target=gene_target,
            total_trials=0,
            active_trials=0,
            completed_trials=0,
            analyzed_trials=0,
            phase_distribution={},
            status_distribution={},
            indication_distribution={},
            top_sponsors=[],
            key_trials=[],
            temporal_trends={},
            summary=f"分析 {gene_target} 时发生错误: {error_msg}",
            confidence_score=0.0,
            last_updated=datetime.now().isoformat(),
            config_used=self._get_config_summary(),
            token_usage={}
        )
    
    # 导出和工具方法
    def export_results(self, result: ClinicalAnalysisResult, format: str = "dict") -> Any:
        """导出分析结果"""
        if format == "dict":
            return asdict(result)
        elif format == "json":
            import json
            return json.dumps(asdict(result), indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_current_config(self) -> AnalysisConfig:
        """获取当前配置"""
        return self.config
    
    def estimate_analysis_cost(self, gene_target: str) -> Dict[str, Any]:
        """估算分析成本"""
        token_estimate = ConfigManager.estimate_token_usage(self.config)
        
        return {
            "gene_target": gene_target,
            "estimated_tokens": token_estimate["total_tokens"],
            "estimated_cost_usd": token_estimate["estimated_cost_usd"],
            "estimated_time_seconds": token_estimate["total_tokens"] // 100,  # 粗略估算
            "config_mode": self.config.mode.value
        }
    
    def __str__(self) -> str:
        return f"ClinicalExpert(name='{self.name}', version='{self.version}', mode='{self.config.mode.value}')"