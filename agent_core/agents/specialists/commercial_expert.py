# agent_core/agents/specialists/commercial_expert.py - 商业分析专家

"""
💰 Commercial Expert - 商业市场分析专家
专注于生物医药市场分析、商业可行性评估和竞争情报
"""

import sys
import os
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

# 项目内部导入
from agent_core.clients.llm_client import call_llm
from agent_core.agents.tools.retrievers.commercial_retriever import (
    CommercialRetriever, 
    MarketInsight,
    MarketAnalysisResult
)
from agent_core.config.analysis_config import AnalysisConfig, AnalysisMode, ConfigManager

logger = logging.getLogger(__name__)

# ===== 分析类型枚举 =====

class MarketAnalysisType(Enum):
    """市场分析类型"""
    COMPREHENSIVE = "comprehensive"      # 综合分析
    MARKET_SIZE = "market_size"         # 市场规模分析
    COMPETITIVE = "competitive"         # 竞争分析
    UNMET_NEEDS = "unmet_needs"        # 未满足需求分析
    REIMBURSEMENT = "reimbursement"    # 市场准入分析
    QUICK = "quick"                     # 快速分析

# ===== 数据结构定义 =====

@dataclass
class CommercialAnalysisRequest:
    """商业分析请求"""
    gene_target: str                    # 靶点基因
    disease: str                        # 相关疾病
    analysis_type: MarketAnalysisType   # 分析类型
    regions: List[str] = None           # 重点分析地区
    competitors: List[str] = None       # 重点竞争对手
    include_forecast: bool = True       # 是否包含预测
    language: str = "zh"                # 输出语言
    
    def __post_init__(self):
        if self.regions is None:
            self.regions = ["Global", "US", "China", "EU"]
        if self.competitors is None:
            self.competitors = []

@dataclass
class MarketAnalysisReport:
    """市场分析报告"""
    gene_target: str
    disease: str
    analysis_type: str
    market_overview: str
    market_size_analysis: str
    unmet_needs_analysis: str
    competitive_landscape: str
    reimbursement_analysis: str
    strategic_recommendations: str
    data_sources: List[Dict[str, str]]
    analysis_timestamp: str
    total_cost: float
    
# ===== 商业分析专家类 =====

class CommercialExpert:
    """商业市场分析专家"""
    
    def __init__(self, config: Optional[AnalysisConfig] = None):
        """
        初始化商业分析专家
        
        Args:
            config: 分析配置
        """
        self.config = config or ConfigManager.get_standard_config()
        self.retriever = CommercialRetriever()
        self.analysis_cache = {}
        
    async def analyze(
        self,
        gene_target: str,
        disease: str,
        analysis_type: MarketAnalysisType = MarketAnalysisType.COMPREHENSIVE,
        **kwargs
    ) -> MarketAnalysisReport:
        """
        执行商业市场分析
        
        Args:
            gene_target: 靶点基因
            disease: 相关疾病
            analysis_type: 分析类型
            **kwargs: 其他参数
            
        Returns:
            市场分析报告
        """
        logger.info(f"开始商业分析: {gene_target} - {disease} ({analysis_type.value})")
        
        # 创建分析请求
        request = CommercialAnalysisRequest(
            gene_target=gene_target,
            disease=disease,
            analysis_type=analysis_type,
            **kwargs
        )
        
        # 检查缓存
        cache_key = self._get_cache_key(request)
        if cache_key in self.analysis_cache:
            logger.info("使用缓存的分析结果")
            return self.analysis_cache[cache_key]
        
        # 获取市场洞察数据
        start_time = datetime.now()
        
        if analysis_type == MarketAnalysisType.QUICK:
            # 快速分析模式
            insights = await self._get_quick_insights(gene_target, disease)
        else:
            # 完整分析模式
            insights = await self._get_comprehensive_insights(gene_target, disease)
        
        # 生成分析报告
        report = await self._generate_analysis_report(request, insights)
        
        # 计算成本
        end_time = datetime.now()
        analysis_time = (end_time - start_time).total_seconds()
        report.total_cost = self._calculate_cost(insights, analysis_time)
        
        # 缓存结果
        self.analysis_cache[cache_key] = report
        
        logger.info(f"商业分析完成，耗时: {analysis_time:.2f}秒，成本: ${report.total_cost:.4f}")
        
        return report
    
    async def _get_quick_insights(self, gene: str, disease: str) -> Dict[str, Any]:
        """快速获取市场洞察"""
        docs = await self.retriever.get_market_insights_async(gene, disease)
        return {
            "documents": docs[:5],  # 限制文档数量
            "structured_data": None
        }
    
    async def _get_comprehensive_insights(self, gene: str, disease: str) -> Dict[str, Any]:
        """获取全面的市场洞察"""
        # 获取非结构化文档
        docs = await self.retriever.get_market_insights_async(gene, disease)
        
        # 获取结构化数据
        structured_data = await asyncio.get_event_loop().run_in_executor(
            None,
            self.retriever.get_structured_insights,
            gene,
            disease
        )
        
        return {
            "documents": docs,
            "structured_data": structured_data
        }
    
    async def _generate_analysis_report(
        self, 
        request: CommercialAnalysisRequest,
        insights: Dict[str, Any]
    ) -> MarketAnalysisReport:
        """生成分析报告"""
        
        # 准备上下文
        docs = insights.get("documents", [])
        structured_data = insights.get("structured_data")
        
        # 构建提示词
        if request.analysis_type == MarketAnalysisType.QUICK:
            prompt = self._build_quick_analysis_prompt(request, docs)
        else:
            prompt = self._build_comprehensive_prompt(request, docs, structured_data)
        
        # 调用LLM生成分析
        try:
            # 调用LLM，call_llm是同步函数，需要在线程池中运行
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, call_llm, prompt)
            
            # 解析响应
            sections = self._parse_analysis_response(response)
            
            # 构建数据源列表
            data_sources = self._extract_data_sources(docs, structured_data)
            
            return MarketAnalysisReport(
                gene_target=request.gene_target,
                disease=request.disease,
                analysis_type=request.analysis_type.value,
                market_overview=sections.get("overview", ""),
                market_size_analysis=sections.get("market_size", ""),
                unmet_needs_analysis=sections.get("unmet_needs", ""),
                competitive_landscape=sections.get("competitive", ""),
                reimbursement_analysis=sections.get("reimbursement", ""),
                strategic_recommendations=sections.get("recommendations", ""),
                data_sources=data_sources,
                analysis_timestamp=datetime.now().isoformat(),
                total_cost=0.0  # 将在外部计算
            )
            
        except Exception as e:
            logger.error(f"生成分析报告失败: {e}")
            raise
    
    def _build_quick_analysis_prompt(
        self, 
        request: CommercialAnalysisRequest,
        docs: List[str]
    ) -> str:
        """构建快速分析提示词"""
        context = "\n\n".join(docs[:3]) if docs else "暂无相关数据"
        
        return f"""
你是一位资深的生物医药商业分析专家，请基于以下信息快速评估市场机会。

目标靶点：{request.gene_target}
相关疾病：{request.disease}

市场信息摘要：
{context}

请提供简洁的市场分析（500字以内），包括：
1. 市场潜力评估（高/中/低）及关键数据支撑
2. 主要市场机会点（2-3个）
3. 关键风险因素（1-2个）
4. 快速行动建议

请用{request.language}输出，返回纯文本格式。
"""
    
    def _build_comprehensive_prompt(
        self,
        request: CommercialAnalysisRequest,
        docs: List[str],
        structured_data: Optional[MarketAnalysisResult]
    ) -> str:
        """构建综合分析提示词"""
        # 控制token长度，只使用前5个最相关的文档
        context = "\n\n".join(docs[:5]) if docs else "暂无相关数据"
        
        # 构建基础提示词
        base_prompt = f"""
你是一位生物医药商业分析专家，擅长从文献、公开数据中总结出市场潜力、未满足需求与商业可行性。

目标靶点：{request.gene_target}
关联疾病：{request.disease}

以下是相关资料（部分年报内容、摘要、市场调研文本）：
---------------------
{context}
---------------------

请基于以上内容，输出结构化市场分析，按以下格式撰写：

## 1. 市场规模与增长趋势
- 全球市场规模（具体数字+年份）
- 主要地区市场分布（美国、欧洲、中国、日本等）
- 年复合增长率（CAGR）
- 未来5-10年市场预测

## 2. 市场空白与未满足需求
- 现有治疗方案的局限性
- 难治性/耐药患者群体规模
- 患者生活质量改善需求
- 新型治疗手段的市场机会

## 3. 竞品销售表现与策略窗口
- 已上市{request.gene_target}靶向药物及销售额
- 主要竞争产品的市场份额
- 在研管线产品进展
- 差异化定位机会

## 4. 市场准入与支付可及性分析
- 各国医保覆盖情况
- 药物定价策略参考
- 患者自付比例和负担能力
- 商业保险覆盖趋势

## 5. 关键成功因素与风险
- 市场进入的关键成功因素
- 主要商业风险及缓解策略
- 合作伙伴选择建议
"""
        
        # 添加额外的分析要求
        additional_requirements = f"""

## 额外分析要求：

1. 重点分析地区：{', '.join(request.regions)}
2. 重点关注竞争对手：{', '.join(request.competitors) if request.competitors else '主要竞争者'}
3. 预测时间范围：{'包含5-10年市场预测' if request.include_forecast else '仅分析当前市场'}
4. 输出语言：{'中文' if request.language == 'zh' else 'English'}

请确保分析具有以下特点：
- 数据驱动：所有结论需有数据支撑
- 可执行性：提供具体的战略建议
- 风险意识：识别并评估主要风险
- 差异化：突出独特的市场定位机会

如无具体数据，请标注"暂无公开数据"，但仍需基于行业经验给出定性分析。
请确保所有数据标注来源和时间。
返回纯markdown格式内容。
"""
        
        return base_prompt + additional_requirements
    
    def _parse_analysis_response(self, response: str) -> Dict[str, str]:
        """解析LLM响应，提取各个章节"""
        sections = {
            "overview": "",
            "market_size": "",
            "unmet_needs": "",
            "competitive": "",
            "reimbursement": "",
            "recommendations": ""
        }
        
        # 简单的章节分割逻辑
        current_section = "overview"
        lines = response.split('\n')
        
        section_markers = {
            "市场规模": "market_size",
            "market size": "market_size",
            "未满足需求": "unmet_needs",
            "unmet need": "unmet_needs",
            "竞品": "competitive",
            "competitive": "competitive",
            "市场准入": "reimbursement",
            "reimbursement": "reimbursement",
            "建议": "recommendations",
            "recommendation": "recommendations"
        }
        
        for line in lines:
            # 检查是否是新章节
            for marker, section_key in section_markers.items():
                if marker.lower() in line.lower() and line.startswith('#'):
                    current_section = section_key
                    break
            
            # 添加内容到当前章节
            sections[current_section] += line + "\n"
        
        return sections
    
    def _extract_data_sources(
        self, 
        docs: List[str],
        structured_data: Optional[MarketAnalysisResult]
    ) -> List[Dict[str, str]]:
        """提取数据源信息"""
        sources = []
        
        # 从结构化数据中提取
        if structured_data:
            for insight_list in [
                structured_data.market_size_data,
                structured_data.competitive_data,
                structured_data.unmet_need_data,
                structured_data.reimbursement_data
            ]:
                for insight in insight_list[:2]:  # 每类取前2个
                    sources.append({
                        "title": insight.title,
                        "url": insight.source_url,
                        "date": insight.published_date,
                        "type": insight.query
                    })
        
        # 确保不重复
        seen_urls = set()
        unique_sources = []
        for source in sources:
            if source["url"] not in seen_urls:
                seen_urls.add(source["url"])
                unique_sources.append(source)
        
        return unique_sources[:10]  # 最多返回10个数据源
    
    def _calculate_cost(self, insights: Dict[str, Any], analysis_time: float) -> float:
        """计算分析成本"""
        # 基础成本
        base_cost = 0.005
        
        # 根据文档数量计算
        doc_count = len(insights.get("documents", []))
        doc_cost = doc_count * 0.0001
        
        # 根据API调用计算（假设每个搜索0.001美元）
        api_cost = 0.01 if insights.get("structured_data") else 0.005
        
        # 时间成本（每分钟0.001美元）
        time_cost = (analysis_time / 60) * 0.001
        
        total_cost = base_cost + doc_cost + api_cost + time_cost
        
        return round(total_cost, 4)
    
    def _get_cache_key(self, request: CommercialAnalysisRequest) -> str:
        """生成缓存键"""
        key_parts = [
            request.gene_target,
            request.disease,
            request.analysis_type.value,
            ','.join(sorted(request.regions)),
            ','.join(sorted(request.competitors))
        ]
        return "|".join(key_parts)
    
    # ===== 便捷方法 =====
    
    async def analyze_market_potential(self, gene: str, disease: str) -> str:
        """快速分析市场潜力"""
        report = await self.analyze(
            gene_target=gene,
            disease=disease,
            analysis_type=MarketAnalysisType.QUICK
        )
        return report.market_overview
    
    async def analyze_competitive_landscape(self, gene: str, disease: str) -> str:
        """分析竞争格局"""
        report = await self.analyze(
            gene_target=gene,
            disease=disease,
            analysis_type=MarketAnalysisType.COMPETITIVE
        )
        return report.competitive_landscape
    
    def format_report(self, report: MarketAnalysisReport) -> str:
        """格式化完整报告"""
        return f"""
# {report.gene_target}靶点 - {report.disease}市场分析报告

**生成时间**: {report.analysis_timestamp}
**分析类型**: {report.analysis_type}
**分析成本**: ${report.total_cost}

## 执行摘要
{report.market_overview}

## 市场规模与增长
{report.market_size_analysis}

## 未满足医疗需求
{report.unmet_needs_analysis}

## 竞争格局分析
{report.competitive_landscape}

## 市场准入与支付
{report.reimbursement_analysis}

## 战略建议
{report.strategic_recommendations}

## 数据来源
""" + "\n".join([f"- [{s['title']}]({s['url']}) ({s['date']})" 
                  for s in report.data_sources[:5]])

# ===== 模块导出 =====

__all__ = [
    "CommercialExpert",
    "MarketAnalysisType", 
    "CommercialAnalysisRequest",
    "MarketAnalysisReport"
]