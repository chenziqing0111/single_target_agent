# agent_core/agents/workers/knowledge_retriever.py (更新版)

import asyncio
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class KnowledgeRetriever:
    """统一知识检索器 - 协调多个专门检索器"""
    
    def __init__(self):
        self.name = "Knowledge Retriever"
        self.version = "2.0.0"
        
        # 延迟导入专门检索器，避免循环依赖
        self._clinical_retriever = None
        self._pubmed_retriever = None
        self._patent_retriever = None
        
    @property
    def clinical_retriever(self):
        """延迟初始化临床试验检索器"""
        if self._clinical_retriever is None:
            from agent_core.agents.tools.retrievers.clinical_trials_retriever import ClinicalTrialsRetriever
            self._clinical_retriever = ClinicalTrialsRetriever()
        return self._clinical_retriever
    
    @property
    def pubmed_retriever(self):
        """延迟初始化PubMed检索器"""
        if self._pubmed_retriever is None:
            # TODO: 实现PubMedRetriever
            from ..tools.retrievers.pubmed_retriever import PubMedRetriever
            self._pubmed_retriever = PubMedRetriever()
        return self._pubmed_retriever
    
    @property
    def patent_retriever(self):
        """延迟初始化专利检索器"""
        if self._patent_retriever is None:
            # TODO: 实现PatentRetriever
            from ..tools.retrievers.patent_retriever import PatentRetriever
            self._patent_retriever = PatentRetriever()
        return self._patent_retriever
    
    async def retrieve_clinical_trials(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        检索临床试验数据
        
        Args:
            query_params: 查询参数
                - gene: 基因名称
                - condition: 适应症（可选）
                - phase: 试验阶段（可选）
                - sponsor: 发起方（可选）
                - max_results: 最大结果数（可选）
        
        Returns:
            Dict containing clinical trials data
        """
        
        try:
            gene = query_params.get("gene", "")
            
            if not gene:
                return self._empty_result("clinical_trials", "基因名称不能为空")
            
            # 使用专门的临床试验检索器
            async with self.clinical_retriever as retriever:
                clean_params = {k: v for k, v in query_params.items() if k != 'gene'}
                trials = await retriever.search_by_gene(gene, **clean_params)
            
            return {
                "source": "clinicaltrials.gov",
                "query": query_params,
                "trials": trials,
                "total_count": len(trials),
                "timestamp": self._get_timestamp(),
                "retriever_version": retriever.version
            }
            
        except Exception as e:
            logger.error(f"临床试验检索失败: {str(e)}")
            return self._error_result("clinical_trials", str(e), query_params)
    
    async def retrieve_pubmed_data(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        检索PubMed文献数据
        
        Args:
            query_params: 查询参数
                - gene: 基因名称
                - keywords: 关键词列表
                - max_results: 最大结果数
        
        Returns:
            Dict containing PubMed literature data
        """
        
        try:
            # TODO: 实现PubMed检索逻辑
            # async with self.pubmed_retriever as retriever:
            #     literature = await retriever.search_literature(**query_params)
            
            # 临时占位符
            literature = []
            
            return {
                "source": "pubmed",
                "query": query_params,
                "literature": literature,
                "total_count": len(literature),
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"PubMed检索失败: {str(e)}")
            return self._error_result("pubmed", str(e), query_params)
    
    async def retrieve_patent_data(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        检索专利数据
        
        Args:
            query_params: 查询参数
                - gene: 基因名称  
                - technology_area: 技术领域
                - assignee: 专利权人
        
        Returns:
            Dict containing patent data
        """
        
        try:
            # TODO: 实现专利检索逻辑
            # async with self.patent_retriever as retriever:
            #     patents = await retriever.search_patents(**query_params)
            
            # 临时占位符
            patents = []
            
            return {
                "source": "patents",
                "query": query_params,
                "patents": patents,
                "total_count": len(patents),
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"专利检索失败: {str(e)}")
            return self._error_result("patents", str(e), query_params)
    
    async def retrieve_all_sources(self, gene: str, sources: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        从多个数据源检索信息
        
        Args:
            gene: 基因名称
            sources: 数据源列表 ['clinical_trials', 'pubmed', 'patents']
            **kwargs: 额外参数
        
        Returns:
            Dict containing data from all sources
        """
        
        if sources is None:
            sources = ['clinical_trials', 'pubmed', 'patents']
        
        results = {}
        tasks = []
        
        # 构建并行任务
        if 'clinical_trials' in sources:
            query_params = {"gene": gene, **kwargs}
            tasks.append(("clinical_trials", self.retrieve_clinical_trials(query_params)))
        
        if 'pubmed' in sources:
            query_params = {"gene": gene, **kwargs}
            tasks.append(("pubmed", self.retrieve_pubmed_data(query_params)))
        
        if 'patents' in sources:
            query_params = {"gene": gene, **kwargs}
            tasks.append(("patents", self.retrieve_patent_data(query_params)))
        
        # 并行执行
        if tasks:
            task_results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            for i, (source_name, _) in enumerate(tasks):
                result = task_results[i]
                if isinstance(result, Exception):
                    results[source_name] = self._error_result(source_name, str(result), {"gene": gene})
                else:
                    results[source_name] = result
        
        # 聚合结果
        aggregated = self._aggregate_results(gene, results)
        
        return aggregated
    
    async def get_trial_details(self, nct_id: str) -> Optional[Dict]:
        """获取特定试验的详细信息"""
        try:
            async with self.clinical_retriever as retriever:
                return await retriever.get_trial_details(nct_id)
        except Exception as e:
            logger.error(f"获取试验详情失败 {nct_id}: {str(e)}")
            return None
    
    async def search_advanced_clinical(self, search_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """高级临床试验搜索"""
        try:
            async with self.clinical_retriever as retriever:
                trials = await retriever.search_advanced(search_criteria)
            
            return {
                "source": "clinicaltrials.gov",
                "search_criteria": search_criteria,
                "trials": trials,
                "total_count": len(trials),
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"高级临床搜索失败: {str(e)}")
            return self._error_result("clinical_trials_advanced", str(e), search_criteria)
    
    def _aggregate_results(self, gene: str, source_results: Dict[str, Dict]) -> Dict[str, Any]:
        """聚合多数据源结果"""
        
        total_items = 0
        successful_sources = []
        failed_sources = []
        
        for source, result in source_results.items():
            if result.get("error"):
                failed_sources.append(source)
            else:
                successful_sources.append(source)
                total_items += result.get("total_count", 0)
        
        return {
            "gene_target": gene,
            "sources_queried": list(source_results.keys()),
            "successful_sources": successful_sources,
            "failed_sources": failed_sources,
            "total_items_retrieved": total_items,
            "source_results": source_results,
            "aggregation_timestamp": self._get_timestamp(),
            "retriever_info": {
                "name": self.name,
                "version": self.version
            }
        }
    
    def _empty_result(self, source: str, message: str) -> Dict[str, Any]:
        """创建空结果"""
        return {
            "source": source,
            "trials": [] if source == "clinical_trials" else [],
            "total_count": 0,
            "message": message,
            "timestamp": self._get_timestamp()
        }
    
    def _error_result(self, source: str, error_msg: str, query: Dict) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "source": source,
            "query": query,
            "trials": [] if source == "clinical_trials" else [],
            "total_count": 0,
            "error": error_msg,
            "timestamp": self._get_timestamp()
        }
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().isoformat()
    
    def get_available_sources(self) -> List[str]:
        """获取可用的数据源列表"""
        return ["clinical_trials", "pubmed", "patents"]
    
    def get_retriever_info(self) -> Dict[str, Any]:
        """获取检索器信息"""
        return {
            "name": self.name,
            "version": self.version,
            "available_sources": self.get_available_sources(),
            "specialized_retrievers": {
                "clinical_trials": "ClinicalTrialsRetriever",
                "pubmed": "PubMedRetriever (TODO)",
                "patents": "PatentRetriever (TODO)"
            }
        }

# 使用示例
async def example_unified_retrieval():
    """统一检索示例"""
    
    retriever = KnowledgeRetriever()
    
    # 1. 单一数据源检索
    print("=== 单一数据源检索 ===")
    clinical_data = await retriever.retrieve_clinical_trials({"gene": "PCSK9"})
    print(f"临床试验数量: {clinical_data['total_count']}")
    
    # 2. 多数据源并行检索
    print("\n=== 多数据源检索 ===")
    all_data = await retriever.retrieve_all_sources("EGFR", sources=["clinical_trials"])
    print(f"成功数据源: {all_data['successful_sources']}")
    print(f"总检索条目: {all_data['total_items_retrieved']}")
    
    # 3. 高级搜索
    print("\n=== 高级搜索 ===")
    advanced_data = await retriever.search_advanced_clinical({
        "gene": "HER2",
        "condition": "breast cancer",
        "phase": ["Phase II", "Phase III"],
        "max_results": 20
    })
    print(f"高级搜索结果: {advanced_data['total_count']}")

if __name__ == "__main__":
    asyncio.run(example_unified_retrieval())