# agent_core/agents/tools/retrievers/pubmed_retriever.py
# 基于你的工作代码改进的PubMed检索器

import asyncio
import concurrent.futures
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from Bio import Entrez

logger = logging.getLogger(__name__)

# 设置Entrez参数
Entrez.email = "czqrainy@gmail.com"
Entrez.api_key = "983222f9d5a2a81facd7d158791d933e6408"

@dataclass
class PubMedArticle:
    """PubMed文章数据结构"""
    pmid: str
    title: str
    abstract: str
    authors: List[str]
    journal: str
    publication_date: str
    doi: Optional[str] = None
    pmc_id: Optional[str] = None
    keywords: Optional[List[str]] = None
    mesh_terms: Optional[List[str]] = None
    url: str = ""
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.mesh_terms is None:
            self.mesh_terms = []
        if not self.url:
            self.url = f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"

@dataclass
class PubMedSearchResult:
    """PubMed搜索结果"""
    query: str
    total_count: int
    retrieved_count: int
    articles: List[PubMedArticle]
    search_timestamp: str
    api_version: str = "2.0.0"

def get_pubmed_abstracts(query: str, retmax: int = 20) -> List[Dict]:
    """
    原始工作函数 - 保持不变以确保兼容性
    返回 Title / Abstract / PMID 的列表
    """
    try:
        # ① esearch：拿 PMID 列表
        ids = Entrez.read(
            Entrez.esearch(db="pubmed", term=query, retmax=retmax)
        )["IdList"]
        
        if not ids:
            return []
        
        # ② efetch：一次性把摘要抓下来（XML）
        root = ET.fromstring(
            Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml").read()
        )
        
        records = []
        for art in root.findall(".//PubmedArticle"):
            pmid = art.findtext(".//PMID")
            title = art.findtext(".//ArticleTitle", default="No title")
            abstract = art.findtext(".//AbstractText", default="No abstract")
            records.append({"PMID": pmid, "Title": title, "Abstract": abstract})
        
        return records
        
    except Exception as e:
        logger.error(f"PubMed检索失败: {e}")
        return []

def get_pubmed_articles_enhanced(query: str, retmax: int = 20) -> List[PubMedArticle]:
    """
    增强版函数 - 提取更多信息
    基于你的工作代码，添加更多字段提取
    """
    try:
        # ① esearch：拿 PMID 列表
        search_result = Entrez.read(
            Entrez.esearch(db="pubmed", term=query, retmax=retmax)
        )
        
        ids = search_result["IdList"]
        
        if not ids:
            return []
        
        # ② efetch：一次性把摘要抓下来（XML）
        xml_content = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml").read()
        root = ET.fromstring(xml_content)
        
        articles = []
        for art in root.findall(".//PubmedArticle"):
            article = _extract_enhanced_article_info(art)
            if article:
                articles.append(article)
        
        return articles
        
    except Exception as e:
        logger.error(f"PubMed增强检索失败: {e}")
        return []

def _extract_enhanced_article_info(article_xml: ET.Element) -> Optional[PubMedArticle]:
    """从XML中提取增强的文章信息"""
    try:
        # 基本信息
        pmid = article_xml.findtext(".//PMID")
        if not pmid:
            return None
        
        title = article_xml.findtext(".//ArticleTitle", default="No title")
        
        # 摘要 - 处理多个AbstractText元素
        abstract_elements = article_xml.findall(".//AbstractText")
        if abstract_elements:
            abstract_parts = []
            for elem in abstract_elements:
                text = elem.text or ""
                label = elem.get('Label', '')
                if label and label.upper() not in ['UNLABELLED']:
                    text = f"{label}: {text}"
                if text.strip():
                    abstract_parts.append(text.strip())
            abstract = " ".join(abstract_parts)
        else:
            abstract = "No abstract available"
        
        # 作者
        authors = []
        for author in article_xml.findall(".//Author"):
            last_name = author.findtext("LastName", "")
            first_name = author.findtext("ForeName", "")
            if last_name and first_name:
                authors.append(f"{last_name}, {first_name}")
            elif last_name:
                authors.append(last_name)
        
        # 期刊信息
        journal = article_xml.findtext(".//Journal/Title", "Unknown Journal")
        if not journal or journal == "Unknown Journal":
            journal = article_xml.findtext(".//Journal/ISOAbbreviation", "Unknown Journal")
        
        # 发表日期
        pub_date = ""
        date_elem = article_xml.find(".//PubDate")
        if date_elem is not None:
            year = date_elem.findtext("Year", "")
            month = date_elem.findtext("Month", "")
            day = date_elem.findtext("Day", "")
            
            if year:
                pub_date = year
                if month:
                    pub_date += f"-{month.zfill(2) if month.isdigit() else month[:3]}"
                    if day:
                        pub_date += f"-{day.zfill(2)}"
        
        # DOI
        doi = None
        for article_id in article_xml.findall(".//ArticleId"):
            if article_id.get('IdType') == 'doi':
                doi = article_id.text
                break
        
        # PMC ID
        pmc_id = None
        for article_id in article_xml.findall(".//ArticleId"):
            if article_id.get('IdType') == 'pmc':
                pmc_id = article_id.text
                break
        
        # MeSH关键词
        mesh_terms = []
        for mesh in article_xml.findall(".//MeshHeading/DescriptorName"):
            if mesh.text:
                mesh_terms.append(mesh.text.strip())
        
        # 关键词
        keywords = []
        for keyword in article_xml.findall(".//Keyword"):
            if keyword.text:
                keywords.append(keyword.text.strip())
        
        return PubMedArticle(
            pmid=pmid,
            title=title.strip() if title else "No title",
            abstract=abstract,
            authors=authors,
            journal=journal,
            publication_date=pub_date,
            doi=doi,
            pmc_id=pmc_id,
            keywords=keywords,
            mesh_terms=mesh_terms
        )
        
    except Exception as e:
        logger.error(f"提取文章信息失败: {e}")
        return None

class PubMedRetriever:
    """
    异步PubMed检索器 - 基于你的工作代码
    在异步环境中运行同步的Bio.Entrez代码
    """
    
    def __init__(self, 
                 email: str = "czqrainy@gmail.com",
                 api_key: Optional[str] = "983222f9d5a2a81facd7d158791d933e6408"):
        self.email = email
        self.api_key = api_key
        
        # 设置Entrez参数
        Entrez.email = email
        if api_key:
            Entrez.api_key = api_key
        
        logger.info(f"初始化PubMed检索器 - 基于工作代码")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def search_literature(self, 
                              query: str, 
                              max_results: int = 20,
                              enhanced: bool = True) -> PubMedSearchResult:
        """
        异步搜索文献
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            enhanced: 是否使用增强信息提取
        
        Returns:
            PubMedSearchResult对象
        """
        search_timestamp = datetime.now().isoformat()
        
        try:
            logger.info(f"搜索PubMed文献: {query} (最多 {max_results} 篇)")
            
            # 在线程池中运行同步代码
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                if enhanced:
                    articles = await loop.run_in_executor(
                        pool, get_pubmed_articles_enhanced, query, max_results
                    )
                else:
                    # 使用原始函数并转换格式
                    raw_results = await loop.run_in_executor(
                        pool, get_pubmed_abstracts, query, max_results
                    )
                    articles = [
                        PubMedArticle(
                            pmid=result["PMID"],
                            title=result["Title"],
                            abstract=result["Abstract"],
                            authors=[],
                            journal="Unknown",
                            publication_date="",
                            keywords=[],
                            mesh_terms=[]
                        )
                        for result in raw_results
                    ]
            
            logger.info(f"成功获取 {len(articles)} 篇文献")
            
            return PubMedSearchResult(
                query=query,
                total_count=len(articles),  # 实际获取的数量
                retrieved_count=len(articles),
                articles=articles,
                search_timestamp=search_timestamp
            )
            
        except Exception as e:
            logger.error(f"文献搜索失败: {e}")
            return PubMedSearchResult(
                query=query,
                total_count=0,
                retrieved_count=0,
                articles=[],
                search_timestamp=search_timestamp
            )
    
    async def search_by_gene(self, 
                           gene: str, 
                           additional_terms: Optional[List[str]] = None,
                           max_results: int = 20) -> PubMedSearchResult:
        """
        按基因名称搜索文献
        
        Args:
            gene: 基因名称
            additional_terms: 额外搜索词
            max_results: 最大结果数
        
        Returns:
            PubMedSearchResult对象
        """
        # 构建简单但有效的查询
        query_parts = [gene]
        
        if additional_terms:
            query_parts.extend(additional_terms)
        
        # 使用简单的AND连接，避免复杂的字段限定符
        query = " AND ".join(query_parts)
        
        return await self.search_literature(query, max_results)


# 测试函数
async def test_working_pubmed_retriever():
    """测试基于工作代码的检索器"""
    print("🧪 测试基于工作代码的PubMed检索器")
    print("=" * 50)
    
    # 首先测试原始函数
    print("1. 测试原始工作函数:")
    try:
        results = get_pubmed_abstracts("BRCA1", retmax=3)
        print(f"   ✅ 原始函数成功: {len(results)} 篇文献")
        
        for i, result in enumerate(results, 1):
            print(f"   文献 {i}: [{result['PMID']}] {result['Title'][:60]}...")
    except Exception as e:
        print(f"   ❌ 原始函数失败: {e}")
    
    print("\n2. 测试增强版函数:")
    try:
        enhanced_results = get_pubmed_articles_enhanced("BRCA1", retmax=3)
        print(f"   ✅ 增强版成功: {len(enhanced_results)} 篇文献")
        
        for i, article in enumerate(enhanced_results, 1):
            print(f"   文献 {i}: [{article.pmid}] {article.title[:60]}...")
            print(f"           期刊: {article.journal}")
            print(f"           作者: {', '.join(article.authors[:2])}...")
    except Exception as e:
        print(f"   ❌ 增强版失败: {e}")
    
    print("\n3. 测试异步检索器:")
    async with PubMedRetriever() as retriever:
        try:
            result = await retriever.search_by_gene("TP53", ["cancer"], max_results=3)
            print(f"   ✅ 异步检索器成功: {result.retrieved_count} 篇文献")
            
            for i, article in enumerate(result.articles, 1):
                print(f"   文献 {i}: [{article.pmid}] {article.title[:60]}...")
                print(f"           期刊: {article.journal}")
                print(f"           日期: {article.publication_date}")
        except Exception as e:
            print(f"   ❌ 异步检索器失败: {e}")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_working_pubmed_retriever())