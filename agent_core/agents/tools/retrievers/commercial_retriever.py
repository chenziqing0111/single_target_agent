# agent_core/agents/tools/retrievers/commercial_retriever.py
# 商业市场洞察检索器

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from dataclasses import dataclass, asdict

from agent_core.tools.web_scraper import search_web

logger = logging.getLogger(__name__)

@dataclass
class MarketInsight:
    """市场洞察数据结构"""
    query: str
    source_url: str
    title: str
    content: str
    summary: str
    relevance_score: float
    published_date: str
    search_timestamp: str
    
@dataclass
class MarketAnalysisResult:
    """市场分析结果"""
    gene_target: str
    disease: str
    total_insights: int
    market_size_data: List[MarketInsight]
    unmet_need_data: List[MarketInsight]
    competitive_data: List[MarketInsight]
    reimbursement_data: List[MarketInsight]
    search_timestamp: str

class CommercialRetriever:
    """商业市场信息检索器"""
    
    def __init__(self):
        self.max_results_per_query = 3
        
    def get_market_insights(self, gene: str, disease: str) -> List[str]:
        """
        基于关键词组合检索可用网页/摘要/年报内容
        
        Args:
            gene: 靶点基因名称
            disease: 相关疾病
            
        Returns:
            市场洞察文档列表
        """
        query_list = [
            f"{disease} market size site:statista.com",
            f"{gene} drug market analysis",
            f"{disease} unmet medical need OR treatment gap",
            f"{gene} inhibitor sales report OR revenue",
            f"{disease} reimbursement China site:cninfo.com.cn",
            f"{disease} epidemiology prevalence incidence",
            f"{gene} {disease} pipeline clinical trials market",
            f"{disease} treatment cost healthcare burden",
            f"{gene} target therapeutic potential commercial",
            f"{disease} patient population addressable market"
        ]
        
        results = []
        for query in query_list:
            logger.info(f"搜索市场信息: {query}")
            try:
                docs = search_web(query, max_results=self.max_results_per_query)
                # 提取内容，优先使用summary，如果没有则使用content的前500字
                for doc in docs:
                    content = doc.get("summary") or doc.get("content", "")[:500]
                    if content:
                        results.append(content)
            except Exception as e:
                logger.error(f"搜索失败 {query}: {e}")
                continue
                
        return results
    
    async def get_market_insights_async(self, gene: str, disease: str) -> List[str]:
        """异步版本的市场洞察检索"""
        query_list = [
            f"{disease} market size site:statista.com",
            f"{gene} drug market analysis", 
            f"{disease} unmet medical need OR treatment gap",
            f"{gene} inhibitor sales report OR revenue",
            f"{disease} reimbursement China site:cninfo.com.cn",
            f"{disease} epidemiology prevalence incidence",
            f"{gene} {disease} pipeline clinical trials market",
            f"{disease} treatment cost healthcare burden",
            f"{gene} target therapeutic potential commercial",
            f"{disease} patient population addressable market"
        ]
        
        async def search_single(query: str) -> List[str]:
            """异步搜索单个查询"""
            try:
                # 在异步环境中运行同步函数
                loop = asyncio.get_event_loop()
                docs = await loop.run_in_executor(
                    None, 
                    search_web, 
                    query, 
                    self.max_results_per_query
                )
                
                results = []
                for doc in docs:
                    content = doc.get("summary") or doc.get("content", "")[:500]
                    if content:
                        results.append(content)
                return results
            except Exception as e:
                logger.error(f"异步搜索失败 {query}: {e}")
                return []
        
        # 并发执行所有搜索
        tasks = [search_single(query) for query in query_list]
        all_results = await asyncio.gather(*tasks)
        
        # 展平结果列表
        flattened = []
        for result_list in all_results:
            flattened.extend(result_list)
            
        return flattened
    
    def get_structured_insights(self, gene: str, disease: str) -> MarketAnalysisResult:
        """
        获取结构化的市场洞察数据
        
        Returns:
            包含分类市场数据的结构化结果
        """
        timestamp = datetime.now().isoformat()
        
        # 市场规模查询
        market_size_queries = [
            f"{disease} market size forecast CAGR",
            f"{disease} global market value billion",
            f"{disease} market size site:statista.com",
            f"{disease} therapeutic market report"
        ]
        
        # 未满足需求查询
        unmet_need_queries = [
            f"{disease} unmet medical need",
            f"{disease} treatment limitations current therapy",
            f"{disease} patient satisfaction treatment gap",
            f"{disease} refractory resistant population"
        ]
        
        # 竞争分析查询
        competitive_queries = [
            f"{gene} inhibitor drug sales revenue",
            f"{gene} {disease} competitive landscape",
            f"{gene} target drug approval market share",
            f"{disease} leading drugs market analysis"
        ]
        
        # 市场准入查询
        reimbursement_queries = [
            f"{disease} reimbursement policy China",
            f"{disease} insurance coverage medicare",
            f"{disease} drug pricing access",
            f"{disease} NRDL inclusion site:cninfo.com.cn"
        ]
        
        # 执行分类搜索
        market_size_data = self._search_insights(market_size_queries, "market_size")
        unmet_need_data = self._search_insights(unmet_need_queries, "unmet_need")
        competitive_data = self._search_insights(competitive_queries, "competitive")
        reimbursement_data = self._search_insights(reimbursement_queries, "reimbursement")
        
        total_insights = (len(market_size_data) + len(unmet_need_data) + 
                         len(competitive_data) + len(reimbursement_data))
        
        return MarketAnalysisResult(
            gene_target=gene,
            disease=disease,
            total_insights=total_insights,
            market_size_data=market_size_data,
            unmet_need_data=unmet_need_data,
            competitive_data=competitive_data,
            reimbursement_data=reimbursement_data,
            search_timestamp=timestamp
        )
    
    def _search_insights(self, queries: List[str], category: str) -> List[MarketInsight]:
        """执行分类搜索并返回MarketInsight对象列表"""
        insights = []
        
        for query in queries:
            try:
                docs = search_web(query, max_results=2)
                for doc in docs:
                    insight = MarketInsight(
                        query=query,
                        source_url=doc.get("url", ""),
                        title=doc.get("title", ""),
                        content=doc.get("content", "")[:1000],  # 限制长度
                        summary=doc.get("summary", ""),
                        relevance_score=doc.get("score", 0.0),
                        published_date=doc.get("published_date", ""),
                        search_timestamp=datetime.now().isoformat()
                    )
                    insights.append(insight)
            except Exception as e:
                logger.error(f"搜索{category}类别失败 {query}: {e}")
                
        return insights
    

# 导出类和函数
__all__ = ["CommercialRetriever", "MarketInsight", "MarketAnalysisResult"]