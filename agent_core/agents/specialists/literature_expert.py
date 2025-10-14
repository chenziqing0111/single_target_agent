# agent_core/agents/specialists/literature_expert.py - 基于RAG的文献分析专家

"""
🧬 Literature Expert - 文献分析专家
支持RAG优化的大规模文献分析，大幅节省Token消耗
"""

import sys
import os
import asyncio
import hashlib
import pickle
import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

# 核心依赖
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    import faiss
except ImportError as e:
    print(f"❌ 缺少必要依赖，请安装: pip install sentence-transformers faiss-cpu")
    raise e

from Bio import Entrez
import xml.etree.ElementTree as ET

# 项目内部导入
from agent_core.clients.llm_client import call_llm
from agent_core.config.analysis_config import AnalysisConfig, AnalysisMode, ConfigManager

logger = logging.getLogger(__name__)

# ===== 查询类型枚举 =====

from enum import Enum

class QueryType(Enum):
    """查询类型"""
    GENE = "gene"                    # 基因查询
    KEYWORD = "keyword"              # 关键词查询
    PROTEIN_FAMILY = "protein_family" # 蛋白家族查询
    MECHANISM = "mechanism"          # 机制查询
    COMPLEX = "complex"              # 复合查询

# ===== 数据结构定义 =====

@dataclass
class SearchQuery:
    """搜索查询结构"""
    query_text: str                 # 查询文本
    query_type: QueryType           # 查询类型
    additional_terms: List[str] = None  # 附加术语
    exclude_terms: List[str] = None     # 排除术语
    date_range: tuple = None            # 日期范围 (start_year, end_year)
    # max_results: int = 500              # 最大结果数
    max_results: int = 10              # 最大结果数

    
    def __post_init__(self):
        if self.additional_terms is None:
            self.additional_terms = []
        if self.exclude_terms is None:
            self.exclude_terms = []

@dataclass
class LiteratureDocument:
    """文献文档结构"""
    pmid: str
    title: str
    abstract: str
    authors: List[str] = None
    journal: str = ""
    year: int = 0
    doi: str = ""
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
    
    def to_text(self) -> str:
        """转换为可搜索的文本"""
        return f"标题: {self.title}\n摘要: {self.abstract}"

@dataclass
class TextChunk:
    """文本块结构"""
    text: str
    doc_id: str  # PMID
    chunk_id: str
    metadata: Dict
    
    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = hashlib.md5(f"{self.doc_id}_{self.text[:50]}".encode()).hexdigest()[:12]

@dataclass
class LiteratureAnalysisResult:
    """文献分析结果"""
    gene_target: str
    disease_mechanism: str
    treatment_strategy: str
    target_analysis: str
    references: List[Dict]
    total_literature: int
    total_chunks: int
    confidence_score: float
    analysis_method: str
    timestamp: str
    config_used: Dict
    token_usage: Dict

# ===== PubMed检索器 =====

class PubMedRetriever:
    """PubMed文献检索器 - 支持多种查询类型"""
    
    def __init__(self):
        self.name = "Enhanced PubMed Retriever"
        self.version = "3.0.0"
        # 配置Bio.Entrez
        Entrez.email = "czqrainy@gmail.com"
        Entrez.api_key = "983222f9d5a2a81facd7d158791d933e6408"
        
        # 预定义的搜索模板
        self.search_templates = {
            QueryType.GENE: [
                "{query}[Title/Abstract]",
                '"{query}" AND (disease OR treatment OR therapy)',
                "{query} AND (clinical trial[Publication Type] OR clinical study[Publication Type])",
                "{query} AND (mechanism OR pathway OR function)",
                "{query} AND (drug OR inhibitor OR target OR therapeutic)"
            ],
            QueryType.KEYWORD: [
                "{query}[Title/Abstract]",
                '"{query}" AND (regulation OR expression OR function)',
                "{query} AND (signaling OR pathway OR mechanism)",
                "{query} AND (therapeutic OR treatment OR clinical)",
                "{query} AND (protein OR gene OR molecular)"
            ],
            QueryType.PROTEIN_FAMILY: [
                '"{query}" AND (protein OR family OR domain)',
                "{query} AND (structure OR function OR binding)",
                "{query} AND (regulation OR expression OR localization)",
                "{query} AND (interaction OR complex OR assembly)",
                "{query} AND (evolution OR conservation OR phylogeny)"
            ],
            QueryType.MECHANISM: [
                '"{query}" AND (mechanism OR pathway OR process)',
                "{query} AND (regulation OR control OR modulation)",
                "{query} AND (signaling OR cascade OR network)",
                "{query} AND (molecular OR cellular OR biological)",
                "{query} AND (function OR role OR activity)"
            ],
            QueryType.COMPLEX: [
                "{query}",  # 复合查询直接使用原始查询
                '"{query}" AND review[Publication Type]',
                "{query} AND recent[Filter]"
            ]
        }
    
    async def search_literature(self, search_query: Union[str, SearchQuery], max_results: int = 10) -> List[LiteratureDocument]:
        """
        检索文献 - 支持多种查询类型
        
        Args:
            search_query: 查询字符串或SearchQuery对象
            max_results: 最大结果数
        
        Returns:
            文献文档列表
        """
        
        # 处理输入参数
        if isinstance(search_query, str):
            # 兼容原有接口：字符串查询默认为基因查询
            query = SearchQuery(
                query_text=search_query,
                query_type=QueryType.GENE,
                max_results=max_results
            )
        else:
            query = search_query
            max_results = query.max_results
        
        print(f"📚 检索文献: {query.query_text} ({query.query_type.value})")
        print(f"   目标: {max_results} 篇")
        
        # 构建搜索策略
        search_strategies = self._build_search_strategies(query)
        
        all_documents = []
        seen_pmids = set()
        
        for strategy in search_strategies:
            print(f"  🔍 搜索策略: {strategy}")
            
            try:
                docs = await self._execute_search(strategy, max_results // len(search_strategies))
                
                for doc in docs:
                    if doc.pmid not in seen_pmids:
                        seen_pmids.add(doc.pmid)
                        all_documents.append(doc)
                        
                        if len(all_documents) >= max_results:
                            break
                
                print(f"    ✅ 新增 {len(docs)} 篇，累计 {len(all_documents)} 篇")
                
                if len(all_documents) >= max_results:
                    break
                    
            except Exception as e:
                print(f"    ❌ 搜索失败: {e}")
                continue
        
        print(f"📊 检索完成: 共 {len(all_documents)} 篇文献")
        return all_documents[:max_results]
    
    def _build_search_strategies(self, query: SearchQuery) -> List[str]:
        """构建搜索策略"""
        
        base_strategies = self.search_templates.get(query.query_type, self.search_templates[QueryType.KEYWORD])
        strategies = []
        
        # 基础查询策略
        for template in base_strategies:
            strategy = template.format(query=query.query_text)
            strategies.append(strategy)
        
        # 添加附加术语
        if query.additional_terms:
            additional_query = f"({query.query_text}) AND ({' OR '.join(query.additional_terms)})"
            strategies.append(additional_query)
        
        # 处理排除术语
        if query.exclude_terms:
            exclude_part = " AND ".join([f"NOT {term}" for term in query.exclude_terms])
            enhanced_strategies = []
            for strategy in strategies[:2]:  # 只对前两个策略应用排除
                enhanced_strategies.append(f"{strategy} {exclude_part}")
            strategies.extend(enhanced_strategies)
        
        # 日期范围过滤
        if query.date_range:
            start_year, end_year = query.date_range
            date_filter = f" AND {start_year}[PDAT]:{end_year}[PDAT]"
            dated_strategies = []
            for strategy in strategies[:3]:  # 对前三个策略应用日期过滤
                dated_strategies.append(f"{strategy}{date_filter}")
            strategies.extend(dated_strategies)
        
        return strategies
    
    async def _execute_search(self, query: str, max_results: int) -> List[LiteratureDocument]:
        """执行单次搜索"""
        
        try:
            # 1. 搜索PMID
            search_handle = Entrez.esearch(
                db="pubmed", 
                term=query, 
                retmax=max_results,
                sort="relevance"
            )
            search_results = Entrez.read(search_handle)
            pmid_list = search_results["IdList"]
            
            if not pmid_list:
                return []
            
            # 2. 批量获取详情
            documents = []
            batch_size = 50
            
            for i in range(0, len(pmid_list), batch_size):
                batch_pmids = pmid_list[i:i+batch_size]
                batch_docs = await self._fetch_batch_details(batch_pmids)
                documents.extend(batch_docs)
                
                # API限流
                if i + batch_size < len(pmid_list):
                    await asyncio.sleep(0.5)
            
            return documents
            
        except Exception as e:
            print(f"❌ 搜索执行失败: {e}")
            return []
    
    async def _fetch_batch_details(self, pmid_list: List[str]) -> List[LiteratureDocument]:
        """批量获取文献详情"""
        
        try:
            fetch_handle = Entrez.efetch(
                db="pubmed",
                id=",".join(pmid_list),
                rettype="medline",
                retmode="xml"
            )
            
            root = ET.fromstring(fetch_handle.read())
            
            documents = []
            for article in root.findall(".//PubmedArticle"):
                doc = self._parse_article(article)
                if doc and doc.abstract:  # 只保留有摘要的
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            print(f"❌ 批量获取失败: {e}")
            return []
    
    def _parse_article(self, article_xml) -> Optional[LiteratureDocument]:
        """解析单篇文章"""
        
        try:
            # 基本信息
            pmid = article_xml.findtext(".//PMID", "")
            title = article_xml.findtext(".//ArticleTitle", "")
            
            # 摘要处理
            abstract_elem = article_xml.find(".//Abstract")
            abstract = ""
            if abstract_elem is not None:
                abstract_texts = []
                for text_elem in abstract_elem.findall(".//AbstractText"):
                    text = text_elem.text or ""
                    label = text_elem.get("Label", "")
                    if label:
                        abstract_texts.append(f"{label}: {text}")
                    else:
                        abstract_texts.append(text)
                abstract = " ".join(abstract_texts)
            
            # 作者
            authors = []
            for author in article_xml.findall(".//Author"):
                last_name = author.findtext("LastName", "")
                first_name = author.findtext("ForeName", "")
                if last_name:
                    authors.append(f"{first_name} {last_name}".strip())
            
            # 期刊和年份
            journal = article_xml.findtext(".//Journal/Title", "")
            year_elem = article_xml.find(".//PubDate/Year")
            year = int(year_elem.text) if year_elem is not None and year_elem.text else 0
            
            # DOI
            doi = ""
            for article_id in article_xml.findall(".//ArticleId"):
                if article_id.get("IdType") == "doi":
                    doi = article_id.text or ""
                    break
            
            if not title or not abstract:
                return None
            
            return LiteratureDocument(
                pmid=pmid,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                year=year,
                doi=doi
            )
            
        except Exception as e:
            return None

# ===== 文本分块器 =====

class SmartChunker:
    """智能文本分块器"""
    
    def __init__(self, chunk_size: int = 250, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_documents(self, documents: List[LiteratureDocument]) -> List[TextChunk]:
        """分块文档"""
        
        print(f"📝 开始文本分块，块大小: {self.chunk_size}")
        
        all_chunks = []
        for doc in documents:
            chunks = self._chunk_single_doc(doc)
            all_chunks.extend(chunks)
        
        print(f"✅ 分块完成: {len(documents)} 篇 → {len(all_chunks)} 块")
        return all_chunks
    
    def _chunk_single_doc(self, doc: LiteratureDocument) -> List[TextChunk]:
        """分块单个文档"""
        
        chunks = []
        
        # 1. 标题块（重要）
        title_chunk = TextChunk(
            text=f"标题: {doc.title}",
            doc_id=doc.pmid,
            chunk_id=f"{doc.pmid}_title",
            metadata={
                "pmid": doc.pmid,
                "title": doc.title,
                "journal": doc.journal,
                "year": doc.year,
                "chunk_type": "title"
            }
        )
        chunks.append(title_chunk)
        
        # 2. 摘要分块
        abstract_chunks = self._chunk_abstract(doc)
        chunks.extend(abstract_chunks)
        
        return chunks
    
    def _chunk_abstract(self, doc: LiteratureDocument) -> List[TextChunk]:
        """分块摘要"""
        
        abstract = doc.abstract
        if len(abstract) <= self.chunk_size:
            # 短摘要，整体作为一块
            return [TextChunk(
                text=f"摘要: {abstract}",
                doc_id=doc.pmid,
                chunk_id=f"{doc.pmid}_abstract",
                metadata={
                    "pmid": doc.pmid,
                    "title": doc.title,
                    "journal": doc.journal,
                    "year": doc.year,
                    "chunk_type": "abstract"
                }
            )]
        
        # 长摘要，按句子分块
        sentences = self._split_sentences(abstract)
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for sentence in sentences:
            test_chunk = current_chunk + " " + sentence if current_chunk else sentence
            
            if len(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                # 保存当前块
                if current_chunk:
                    chunks.append(TextChunk(
                        text=f"摘要: {current_chunk}",
                        doc_id=doc.pmid,
                        chunk_id=f"{doc.pmid}_abstract_{chunk_index}",
                        metadata={
                            "pmid": doc.pmid,
                            "title": doc.title,
                            "journal": doc.journal,
                            "year": doc.year,
                            "chunk_type": "abstract_part",
                            "part_index": chunk_index
                        }
                    ))
                    chunk_index += 1
                
                current_chunk = sentence
        
        # 最后一块
        if current_chunk:
            chunks.append(TextChunk(
                text=f"摘要: {current_chunk}",
                doc_id=doc.pmid,
                chunk_id=f"{doc.pmid}_abstract_{chunk_index}",
                metadata={
                    "pmid": doc.pmid,
                    "title": doc.title,
                    "journal": doc.journal,
                    "year": doc.year,
                    "chunk_type": "abstract_part",
                    "part_index": chunk_index
                }
            ))
        
        return chunks
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        
        sentences = []
        current = ""
        
        for i, char in enumerate(text):
            current += char
            if char in '.!?' and i + 1 < len(text) and text[i + 1] in ' \n':
                sentences.append(current.strip())
                current = ""
        
        if current.strip():
            sentences.append(current.strip())
        
        return [s for s in sentences if len(s) > 10]

# ===== 向量存储系统 =====

class VectorStore:
    """向量存储和检索"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.encoder = SentenceTransformer(model_name)
        self.index = None
        self.chunks = []
    
    def build_index(self, chunks: List[TextChunk]):
        """构建向量索引"""
        
        print(f"🔍 构建向量索引，模型: {self.model_name}")
        
        self.chunks = chunks
        texts = [chunk.text for chunk in chunks]
        
        print(f"  📊 编码 {len(texts)} 个文本块...")
        embeddings = self.encoder.encode(texts, show_progress_bar=True)
        
        # 构建FAISS索引
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        
        # 标准化用于余弦相似度
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings.astype('float32'))
        
        print(f"✅ 索引构建完成: {len(chunks)} 块, 维度: {dimension}")
    
    def search(self, query: str, top_k: int = 15) -> List[Dict]:
        """搜索相关块"""
        
        if self.index is None:
            raise ValueError("索引未构建")
        
        # 编码查询
        query_embedding = self.encoder.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # 搜索
        scores, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        # 构建结果
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.chunks):
                chunk = self.chunks[idx]
                results.append({
                    "chunk": chunk,
                    "score": float(score),
                    "text": chunk.text,
                    "metadata": chunk.metadata
                })
        
        return results
    
    def save(self, file_path: str):
        """保存索引"""
        
        save_data = {
            "chunks": self.chunks,
            "model_name": self.model_name
        }
        
        with open(file_path, 'wb') as f:
            pickle.dump(save_data, f)
        
        faiss.write_index(self.index, file_path + ".faiss")
        print(f"💾 索引已保存: {file_path}")
    
    def load(self, file_path: str) -> bool:
        """加载索引"""
        
        try:
            with open(file_path, 'rb') as f:
                save_data = pickle.load(f)
            
            self.chunks = save_data["chunks"]
            self.model_name = save_data["model_name"]
            self.index = faiss.read_index(file_path + ".faiss")
            
            print(f"📂 索引已加载: {len(self.chunks)} 块")
            return True
            
        except Exception as e:
            print(f"❌ 加载失败: {e}")
            return False

# ===== RAG查询处理器 =====

class RAGProcessor:
    """RAG查询处理器"""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.query_templates = {
            "disease_mechanism": "该基因与哪些疾病相关？疾病的发病机制是什么？有什么临床需求？",
            "treatment_strategy": "有哪些治疗方法和策略？包括药物、疗法等？临床研究现状如何？",
            "target_analysis": "该基因的作用通路是什么？有哪些潜在治疗靶点？研究进展如何？"
        }
    
    async def process_query(self, gene: str, query_type: str, top_k: int = 15) -> str:
        """处理RAG查询"""
        
        print(f"🤖 RAG查询: {gene} - {query_type}")
        
        # 构建查询
        base_query = self.query_templates.get(query_type, "")
        full_query = f"{gene} {base_query}"
        
        # 检索相关块
        relevant_chunks = self.vector_store.search(full_query, top_k)
        
        if not relevant_chunks:
            return f"未找到与 {gene} 相关的 {query_type} 信息。"
        
        print(f"  📊 检索到 {len(relevant_chunks)} 个相关块")
        
        # 构建prompt
        prompt = self._build_prompt(gene, query_type, relevant_chunks)
        
        # LLM生成
        response = call_llm(prompt)
        return response
    
    def _build_prompt(self, gene: str, query_type: str, relevant_chunks: List[Dict]) -> str:
        """构建RAG prompt - 基于文献的引用系统"""
        
        # 按PMID分组chunks，创建文献映射
        pmid_to_literature = {}
        literature_counter = 1
        
        # 为每个唯一PMID分配文献编号
        seen_pmids = set()
        for chunk_info in relevant_chunks:
            chunk = chunk_info["chunk"]
            pmid = chunk.metadata.get("pmid", "")
            if pmid and pmid not in seen_pmids:
                pmid_to_literature[pmid] = f"文献{literature_counter}"
                literature_counter += 1
                seen_pmids.add(pmid)
        
        # 整理上下文，使用文献编号标记
        context_blocks = []
        references_text = "\n\n## 参考文献\n"
        
        for i, chunk_info in enumerate(relevant_chunks):
            chunk = chunk_info["chunk"]
            score = chunk_info["score"]
            pmid = chunk.metadata.get("pmid", "")
            
            # 获取文献编号
            if pmid in pmid_to_literature:
                lit_ref = pmid_to_literature[pmid]
                context_blocks.append(f"[{i+1}] 来源{lit_ref}: {chunk.text}")
            else:
                context_blocks.append(f"[{i+1}] {chunk.text}")
        
        # 生成参考文献列表
        for pmid, lit_ref in pmid_to_literature.items():
            # 从chunks中获取文献信息
            for chunk_info in relevant_chunks:
                chunk = chunk_info["chunk"]
                if chunk.metadata.get("pmid") == pmid:
                    title = chunk.metadata.get("title", "")
                    journal = chunk.metadata.get("journal", "")
                    year = chunk.metadata.get("year", "")
                    references_text += f"{lit_ref}: PMID:{pmid}, {title}, {journal}, {year}\n"
                    break
        
        context_text = "\n\n".join(context_blocks)
        
        # ===== 基因查询相关 Prompts =====
        if query_type == "disease_mechanism":
            prompt = f"""你是资深医学专家，请基于以下文献信息深入分析基因 {gene} 的疾病机制。

请仔细阅读以下相关文献段落，并基于这些信息进行回答。在引用时，请使用对应的文献编号（如文献1、文献2等）。

相关文献段落：
{context_text}

请进行详细分析，在适当位置添加引用。

{references_text}

请以如下结构输出：
### 疾病机制与临床需求分析（Gene: {gene}）

#### 1. 疾病关联谱
- **强关联疾病**（直接致病基因）：
  - 疾病名称 | 遗传模式 | 患病率 | 证据等级 [文献X]
- **中等关联疾病**（易感基因）：
  - 疾病名称 | OR值/RR值 | 人群频率 | 证据来源 [文献X]
- **弱关联疾病**（可能相关）：
  - 疾病名称 | 研究现状 | 争议点 [文献X]

#### 2. 分子病理机制
- **正常生理功能**：
  - 蛋白功能域和活性位点
  - 信号通路和调控网络
  - 组织表达谱和亚细胞定位
- **致病机制**：
  - 功能丧失型变异（LoF）：具体影响
  - 功能获得型变异（GoF）：机制描述
  - 主导负效应（Dominant negative）：分子基础
- **基因型-表型关联**：
  - 特定变异与临床表现的对应关系 [文献X]

#### 3. 临床需求评估
- **已有治疗手段**：
  - 药物治疗：具体药物和疗效
  - 基因治疗：进展和挑战
  - 其他干预：效果评价
- **未满足需求**：
  - 治疗空白：哪些亚型/阶段缺乏有效治疗
  - 疗效局限：现有治疗的不足
  - 安全性问题：副作用和风险
- **机会识别**：
  - 新靶点：基于机制的潜在干预位点
  - 新策略：创新治疗思路
  - 优先级：按可行性和影响力排序

#### 4. 研究趋势与展望
- 近期研究热点 [文献X]
- 技术突破和新发现
- 未来研究方向建议

注意：只基于提供的文献信息回答，不要添加未提及的内容。对于不确定的信息，请明确标注"文献未明确说明"。"""

        elif query_type == "treatment_strategy":
            prompt = f"""你是临床医学和药物开发专家，请基于以下文献信息全面分析基因 {gene} 相关的治疗策略。

分析维度：
1. 系统梳理所有治疗方法（已上市、临床试验、临床前）
2. 评估各治疗策略的效果、安全性和适用人群
3. 比较不同治疗方案的优劣势
4. 识别联合治疗机会和个体化治疗策略
5. 预测未来治疗发展方向

请仔细阅读以下相关文献段落，并基于这些信息进行回答。在引用具体信息时，请使用 [文献1]、[文献2] 等标记（对应上述文献编号）。

相关文献段落：
{context_text}

请以如下结构输出：
### 治疗策略综合分析（Gene: {gene}）

#### 1. 治疗方法全景图
- **已上市治疗**：
  - 小分子药物：名称 | 作用机制 | 适应症 | 关键临床数据 [文献X]
  - 生物制剂：类型 | 靶点 | 疗效 | 安全性 [文献X]
  - 基因/细胞治疗：技术平台 | 临床应用 | 长期随访 [文献X]
- **临床试验阶段**：
  - III期：药物 | 入组标准 | 主要终点 | 预期完成时间 [文献X]
  - II期：创新点 | 初步疗效 | 安全性信号 [文献X]
  - I期：新机制 | 剂量探索 | 早期信号 [文献X]
- **临床前研究**：
  - 新靶点验证：实验证据 | 转化潜力 [文献X]
  - 新技术应用：CRISPR、ASO、siRNA等 [文献X]

#### 2. 疗效与安全性评估
- **疗效对比分析**：
  - 客观缓解率（ORR）、无进展生存期（PFS）、总生存期（OS）比较
  - 生物标志物与疗效预测
  - 真实世界数据 vs 临床试验数据
- **安全性概况**：
  - 常见不良反应：发生率和处理策略
  - 严重不良事件：风险因素和监测方案
  - 特殊人群考虑：儿童、老年、肝肾功能不全

#### 3. 个体化治疗策略
- **生物标志物指导**：
  - 预测标志物：基因型、表达水平、蛋白活性
  - 监测标志物：疗效评估、耐药预警
- **联合治疗方案**：
  - 理论基础：协同机制
  - 临床证据：联合 vs 单药
  - 最佳组合：推荐方案
- **序贯治疗策略**：
  - 一线、二线、三线选择逻辑
  - 耐药后策略

#### 4. 创新治疗展望
- **突破性疗法**：技术创新点和临床转化前景 [文献X]
- **精准医疗实践**：从基因检测到治疗决策的路径
- **未来5-10年预测**：可能改变治疗格局的进展

注意：请严格基于文献证据，对于推测性内容需明确标注。"""

        elif query_type == "target_analysis":
            prompt = f"""你是药物靶点研究和新药开发专家，请基于以下文献信息深入分析基因 {gene} 的成药性和靶点开发策略。

分析框架：
1. 靶点可成药性（Druggability）多维度评估
2. 结构生物学基础和药物设计策略
3. 靶点验证证据链和转化医学考虑
4. 知识产权格局和竞争态势
5. 开发风险评估和缓解策略

请仔细阅读以下相关文献段落，并基于这些信息进行回答。在引用具体信息时，请使用 [文献1]、[文献2] 等标记（对应上述文献编号）。

相关文献段落：
{context_text}

请以如下结构输出：
### 靶点成药性与开发策略分析（Gene: {gene}）

#### 1. 靶点可成药性评估
- **蛋白结构特征**：
  - 已解析结构：PDB ID | 分辨率 | 关键功能域 [文献X]
  - 可结合口袋：位置 | 大小 | 疏水性 | 可及性评分
  - 变构位点：已知/预测位点及调控机制
- **化学可干预性**：
  - 小分子结合：已知配体 | 亲和力 | 选择性 [文献X]
  - 生物大分子：抗体、多肽、核酸适配体可行性
  - 新模态：PROTAC、分子胶、共价抑制剂潜力
- **生物学可行性**：
  - 靶点选择性：避免脱靶效应的策略
  - 组织分布：靶器官可及性
  - 补偿机制：潜在耐药通路

#### 2. 靶点验证强度
- **遗传学证据**：
  - 人类遗传学：GWAS、罕见变异、家系研究 [文献X]
  - 功能缺失/获得型变异的表型
  - 基因剂量效应
- **药理学验证**：
  - 工具化合物：活性、选择性、体内效果 [文献X]
  - 基因敲除/敲减：表型救援实验
  - 生物标志物：靶点占有率与效果关系
- **临床验证**：
  - 概念验证研究：早期临床信号 [文献X]
  - 失败案例分析：原因和启示

#### 3. 药物设计策略
- **基于结构的设计（SBDD）**：
  - 先导化合物：来源和优化策略
  - 构效关系（SAR）：关键药效团
  - 计算辅助：分子对接、动力学模拟
- **基于表型的筛选**：
  - 筛选模型：细胞系、类器官、动物模型
  - 检测指标：与临床终点的相关性
- **新技术应用**：
  - AI/ML在先导物发现中的应用
  - DNA编码化合物库（DEL）
  - Fragment-based drug discovery（FBDD）

#### 4. 转化医学考虑
- **患者分层策略**：
  - 生物标志物开发：伴随诊断
  - 适应症选择：优先级排序
- **临床开发路径**：
  - 注册路径：孤儿药、突破性疗法认定可能性
  - 临床试验设计：终点选择、样本量估算
- **商业化潜力**：
  - 市场规模：患者人数、治疗渗透率
  - 竞争格局：在研管线分析
  - 差异化定位：独特价值主张

#### 5. 风险与机遇
- **技术风险**：主要挑战和应对方案
- **监管风险**：潜在的安全性担忧
- **商业风险**：IP壁垒、市场接受度
- **机遇窗口**：时间敏感性分析

注意：评估应基于文献证据，对推测性判断需注明依据。"""


        elif query_type == "mechanism_pathway":
            prompt = f"""你是分子生物学和系统生物学专家，请基于以下文献深入解析与 "{gene}" 相关的分子机制和信号通路。

分析重点：
1. 核心信号通路的详细解析
2. 调控网络和反馈机制
3. 时空动态和细胞特异性
4. 与疾病的机制联系
5. 潜在的干预节点

相关文献段落：
{context_text}

请以如下结构输出：
### 分子机制与通路解析：{gene}

#### 1. 核心信号通路
- **经典通路**：
  - 通路名称：关键分子 → 中间步骤 → 下游效应 [文献X]
  - 调控机制：激活/抑制条件、反馈环路
  - 生理功能：正常状态下的作用
- **新发现通路**：
  - 非经典激活：新的上游信号或激活模式 [文献X]
  - 交叉对话：与其他通路的相互作用
  - 细胞类型特异性：不同细胞中的差异

#### 2. 分子相互作用网络
- **直接相互作用**：
  - 蛋白-蛋白：结合界面、亲和力、功能影响 [文献X]
  - 蛋白-核酸：结合序列、调控模式
  - 翻译后修饰：类型、位点、功能后果
- **间接调控**：
  - 转录调控：转录因子、增强子、表观遗传
  - 代谢调控：代谢物反馈、能量感应
  - 微环境因素：pH、氧浓度、机械力

#### 3. 时空动态调控
- **时间动态**：
  - 快速响应（分钟级）：磷酸化级联
  - 中期适应（小时级）：转录重编程
  - 长期重塑（天-周）：表观遗传改变
- **空间分布**：
  - 亚细胞定位：定位信号、转运机制
  - 组织特异性：表达谱、功能差异
  - 发育阶段性：时序表达、功能转换

#### 4. 病理状态改变
- **失调机制**：正常→疾病的分子事件链 [文献X]
- **代偿机制**：机体的适应性改变
- **治疗靶点**：可干预的关键节点

注意：优先引用最新研究，注意机制的争议和不确定性。"""

        else:
            # 通用prompt处理其他query_type
            prompt = f"""请基于以下文献信息分析基因 {gene} 的 {query_type}。

请仔细阅读以下相关文献段落，并基于这些信息进行回答。在引用时，请使用对应的文献编号（如文献1、文献2等）。

相关文献段落：
{context_text}

请进行详细分析，在适当位置添加引用。

{references_text}"""

        return prompt
# ===== 缓存管理器 =====

class CacheManager:
    """增强的缓存管理器"""
    
    def __init__(self, cache_dir: str = "enhanced_literature_cache"):
        self.cache_dir = cache_dir
        self.cache_days = 7  # 缓存有效期
        os.makedirs(cache_dir, exist_ok=True)
    
    def load_by_key(self, cache_key: str) -> Optional[VectorStore]:
        """根据缓存键加载"""
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            # 检查缓存时效
            mod_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - mod_time > timedelta(days=self.cache_days):
                return None
            
            with open(cache_file, 'rb') as f:
                vector_store = pickle.load(f)
                print(f"📂 从缓存加载: {cache_key}")
                return vector_store
                
        except Exception as e:
            print(f"❌ 缓存加载失败: {e}")
            return None
    
    def save_by_key(self, cache_key: str, vector_store: VectorStore):
        """根据缓存键保存"""
        
        try:
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
            with open(cache_file, 'wb') as f:
                pickle.dump(vector_store, f)
            print(f"💾 缓存已保存: {cache_key}")
        except Exception as e:
            print(f"❌ 缓存保存失败: {e}")
    
    # 兼容原有接口
    def get_cache_path(self, gene: str, max_results: int) -> str:
        """获取缓存路径"""
        cache_key = f"{gene}_{max_results}"
        return os.path.join(self.cache_dir, f"{cache_key}")
    
    def is_valid(self, cache_path: str, max_age_days: int = 7) -> bool:
        """检查缓存是否有效"""
        if not os.path.exists(cache_path):
            return False
        
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        return datetime.now() - file_time < timedelta(days=max_age_days)
    
    def save(self, gene: str, max_results: int, vector_store: VectorStore):
        """兼容原有save方法"""
        cache_key = f"{gene}_{max_results}"
        self.save_by_key(cache_key, vector_store)
    
    def load(self, gene: str, max_results: int) -> Optional[VectorStore]:
        """兼容原有load方法"""
        cache_key = f"{gene}_{max_results}"
        return self.load_by_key(cache_key)

# ===== 主要的Literature Expert =====

class LiteratureExpert:
    """文献分析专家 - 基于RAG优化，支持多种查询类型"""
    
    def __init__(self, config: AnalysisConfig = None):
        self.name = "Enhanced Literature Expert"
        self.version = "3.0.0"
        self.expertise = ["多类型查询", "文献分析", "机制研究", "治疗策略", "靶点分析"]
        
        # 配置
        self.config = config or ConfigManager.get_standard_config()
        
        # 组件
        self.retriever = PubMedRetriever()
        self.chunker = SmartChunker(chunk_size=250, overlap=50)
        self.cache_manager = CacheManager()
        
        logger.info(f"Literature Expert 初始化完成 - {self.version}")
    
    def set_config(self, config: AnalysisConfig):
        """设置配置"""
        self.config = config
        logger.info(f"配置已更新: {config.mode.value}")
    
    def set_mode(self, mode: AnalysisMode):
        """设置模式"""
        self.config = ConfigManager.get_config_by_mode(mode)
        logger.info(f"模式切换: {mode.value}")
    
    async def analyze(self, gene_target: str, context: Dict[str, Any] = None) -> LiteratureAnalysisResult:
        """
        主要分析方法（基因名查询）
        
        Args:
            gene_target: 目标基因
            context: 上下文配置
        
        Returns:
            文献分析结果
        """
        
        return await self.analyze_by_gene(gene_target, context)
    
    async def analyze_by_gene(self, gene_target: str, context: Dict[str, Any] = None) -> LiteratureAnalysisResult:
        """基因名分析"""
        
        query = SearchQuery(
            query_text=gene_target,
            query_type=QueryType.GENE,
            max_results=self._get_max_literature()
        )
        
        return await self.analyze_by_query(query, context)
    
    async def analyze_by_keyword(self, keyword: str, 
                                additional_terms: List[str] = None,
                                exclude_terms: List[str] = None,
                                context: Dict[str, Any] = None) -> LiteratureAnalysisResult:
        """关键词分析"""
        
        query = SearchQuery(
            query_text=keyword,
            query_type=QueryType.KEYWORD,
            additional_terms=additional_terms or [],
            exclude_terms=exclude_terms or [],
            max_results=self._get_max_literature()
        )
        
        return await self.analyze_by_query(query, context)
    
    async def analyze_protein_family(self, family_name: str,
                                   additional_terms: List[str] = None,
                                   context: Dict[str, Any] = None) -> LiteratureAnalysisResult:
        """蛋白家族分析"""
        
        query = SearchQuery(
            query_text=family_name,
            query_type=QueryType.PROTEIN_FAMILY,
            additional_terms=additional_terms or [],
            max_results=self._get_max_literature()
        )
        
        return await self.analyze_by_query(query, context)
    
    async def analyze_mechanism(self, mechanism_query: str,
                              additional_terms: List[str] = None,
                              context: Dict[str, Any] = None) -> LiteratureAnalysisResult:
        """机制分析"""
        
        query = SearchQuery(
            query_text=mechanism_query,
            query_type=QueryType.MECHANISM,
            additional_terms=additional_terms or [],
            max_results=self._get_max_literature()
        )
        
        return await self.analyze_by_query(query, context)
    
    async def analyze_by_query(self, search_query: SearchQuery, context: Dict[str, Any] = None) -> LiteratureAnalysisResult:
        """
        通用查询分析方法
        
        Args:
            search_query: 搜索查询对象
            context: 上下文配置
        
        Returns:
            文献分析结果
        """
        
        logger.info(f"开始文献分析: {search_query.query_text} ({search_query.query_type.value}) - 模式: {self.config.mode.value}")
        
        try:
            # 确定分析参数
            top_k = self._get_top_k()
            
            # 1. 尝试从缓存加载
            cache_key = self._generate_cache_key(search_query)
            vector_store = self.cache_manager.load_by_key(cache_key)
            
            # 2. 如果缓存无效，重新构建
            if vector_store is None:
                vector_store = await self._build_literature_index_async(search_query)
                # 保存缓存
                self.cache_manager.save_by_key(cache_key, vector_store)
            
            # 3. RAG查询处理
            rag_processor = RAGProcessor(vector_store)
            
            print("🤖 开始RAG查询...")
            
            # 根据查询类型调整RAG查询
            rag_queries = self._get_rag_queries(search_query)
            
            # 并发处理查询
            tasks = [
                rag_processor.process_query(search_query.query_text, query_type, top_k)
                for query_type in rag_queries
            ]
            
            results = await asyncio.gather(*tasks)
            
            # 4. 构建分析结果
            references = self._extract_references(vector_store.chunks)
            confidence_score = self._calculate_confidence(vector_store.chunks)
            
            # 根据查询类型组织结果
            result_dict = {}
            for i, query_type in enumerate(rag_queries):
                result_dict[query_type] = results[i] if i < len(results) else ""
            
            analysis_result = LiteratureAnalysisResult(
                gene_target=search_query.query_text,  # 保持兼容性
                disease_mechanism=result_dict.get("disease_mechanism", ""),
                treatment_strategy=result_dict.get("treatment_strategy", ""),
                target_analysis=result_dict.get("target_analysis", ""),
                references=references[:50],  # 限制引用数量
                total_literature=len(set(chunk.doc_id for chunk in vector_store.chunks)),
                total_chunks=len(vector_store.chunks),
                confidence_score=confidence_score,
                analysis_method=f"Enhanced-RAG-{search_query.query_type.value}",
                timestamp=datetime.now().isoformat(),
                config_used=self._get_config_summary(),
                token_usage=self._estimate_token_usage(top_k)
            )
            
            logger.info(f"文献分析完成: {search_query.query_text} - 文献数: {analysis_result.total_literature}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"文献分析失败: {search_query.query_text} - {str(e)}")
            return self._create_error_result(search_query.query_text, str(e))
    
    def _get_rag_queries(self, search_query: SearchQuery) -> List[str]:
        """根据查询类型获取RAG查询类型"""
        
        # 所有查询类型都使用标准的三个分析维度
        return ["disease_mechanism", "treatment_strategy", "target_analysis"]
    
    def _generate_cache_key(self, search_query: SearchQuery) -> str:
        """生成缓存键"""
        
        query_str = f"{search_query.query_text}_{search_query.query_type.value}"
        if search_query.additional_terms:
            query_str += f"_add_{','.join(search_query.additional_terms)}"
        if search_query.exclude_terms:
            query_str += f"_exc_{','.join(search_query.exclude_terms)}"
        if search_query.date_range:
            query_str += f"_date_{search_query.date_range[0]}_{search_query.date_range[1]}"
        
        return hashlib.md5(query_str.encode()).hexdigest()
    
    async def _build_literature_index_async(self, search_query: SearchQuery) -> VectorStore:
        """构建文献索引"""
        
        print(f"🏗️ 构建文献索引: {search_query.query_text} ({search_query.query_type.value})")
        
        # 1. 检索文献
        documents = await self.retriever.search_literature(search_query)
        
        if not documents:
            raise ValueError(f"未找到 {search_query.query_text} 相关文献")
        
        # 2. 文本分块
        chunks = self.chunker.chunk_documents(documents)
        
        # 3. 构建向量索引
        vector_store = VectorStore()
        vector_store.build_index(chunks)
        
        return vector_store
    
    def _get_max_literature(self) -> int:
        """获取最大文献数量"""
        if self.config.mode == AnalysisMode.QUICK:
            return 100
        elif self.config.mode == AnalysisMode.STANDARD:
            return 500
        elif self.config.mode == AnalysisMode.DEEP:
            # return 1000
            return 10
        else:
            return 500
    
    def _get_top_k(self) -> int:
        """获取top-k参数"""
        if self.config.mode == AnalysisMode.QUICK:
            return 25
        elif self.config.mode == AnalysisMode.STANDARD:
            return 100
        elif self.config.mode == AnalysisMode.DEEP:
            # return 300
            return 10
        else:
            return 50
    
    def _extract_references(self, chunks: List[TextChunk]) -> List[Dict]:
        """提取引用信息"""
        
        references = {}
        for chunk in chunks:
            pmid = chunk.metadata.get("pmid", "")
            if pmid and pmid not in references:
                references[pmid] = {
                    "PMID": pmid,
                    "Title": chunk.metadata.get("title", ""),
                    "Journal": chunk.metadata.get("journal", ""),
                    "Year": chunk.metadata.get("year", 0)
                }
        
        return list(references.values())
    
    def _calculate_confidence(self, chunks: List[TextChunk]) -> float:
        """计算置信度"""
        
        if not chunks:
            return 0.0
        
        # 基于文献数量和质量的简单评分
        unique_docs = len(set(chunk.doc_id for chunk in chunks))
        
        if unique_docs >= 50:
            return 0.9
        elif unique_docs >= 20:
            return 0.8
        elif unique_docs >= 10:
            return 0.7
        elif unique_docs >= 5:
            return 0.6
        else:
            return 0.5
    
    def _estimate_token_usage(self, top_k: int) -> Dict:
        """估算Token使用"""
        
        # RAG方式的Token估算
        input_tokens = top_k * 200  # 每个相关块约200 tokens
        output_tokens = 10000 * 3   # 三个问题各1000 tokens输出
        total_tokens = input_tokens + output_tokens
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": total_tokens * 0.000002
        }
    
    def _get_config_summary(self) -> Dict:
        """获取配置摘要"""
        
        return {
            "mode": self.config.mode.value,
            "max_literature": self._get_max_literature(),
            "top_k": self._get_top_k(),
            "analysis_method": "RAG-optimized"
        }
    
    def _create_error_result(self, gene_target: str, error_msg: str) -> LiteratureAnalysisResult:
        """创建错误结果"""
        
        return LiteratureAnalysisResult(
            gene_target=gene_target,
            disease_mechanism=f"分析 {gene_target} 时发生错误: {error_msg}",
            treatment_strategy="",
            target_analysis="",
            references=[],
            total_literature=0,
            total_chunks=0,
            confidence_score=0.0,
            analysis_method="error",
            timestamp=datetime.now().isoformat(),
            config_used=self._get_config_summary(),
            token_usage={}
        )
    
    def export_results(self, result: LiteratureAnalysisResult, format: str = "dict") -> Any:
        """导出结果"""
        
        if format == "dict":
            return asdict(result)
        elif format == "json":
            import json
            return json.dumps(asdict(result), indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"不支持的格式: {format}")
    
    def estimate_analysis_cost(self, gene_target: str) -> Dict[str, Any]:
        """估算分析成本"""
        
        token_estimate = self._estimate_token_usage(self._get_top_k())
        
        return {
            "gene_target": gene_target,
            "estimated_tokens": token_estimate["total_tokens"],
            "estimated_cost_usd": token_estimate["estimated_cost_usd"],
            "estimated_time_seconds": 60,  # RAG分析约1分钟
            "config_mode": self.config.mode.value,
            "max_literature": self._get_max_literature()
        }
    
    def __str__(self) -> str:
        return f"LiteratureExpert(name='{self.name}', version='{self.version}', mode='{self.config.mode.value}')"

