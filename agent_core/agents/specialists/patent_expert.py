import asyncio
from dataclasses import dataclass
from typing import Dict, List
import requests
import json
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from IPython.display import display, HTML
import re
from openai import OpenAI

@dataclass
class PatentAnalysisResult:
    """统一的返回格式"""
    total_patents: int = 0
    analyzed_patents: int = 0
    report: str = ""
    statistics: Dict = None
    detailed_analyses: List = None
    cost: float = 0.0
    duration: float = 0.0
    raw_data: Dict = None

class PatentExpert:
    """最小封装 - 只包装原始的Pipeline"""
    
    def __init__(self, config=None):
        self.config = config or {}
        # 直接使用您原始的PatentAnalysisPipeline
        self.pipeline = PatentAnalysisPipeline()
    
    async def analyze(self, gene_name: str, disease: str = None) -> PatentAnalysisResult:
        """
        调用原始的分析流程
        """
        # 直接调用您原始的run_complete_analysis
        results = self.pipeline.run_complete_analysis(gene_name)
        
        # 转换为标准返回格式
        if results:
            return PatentAnalysisResult(
                total_patents=results.get("statistics", {}).get("total_patents", 0),
                analyzed_patents=len(results.get("detailed_analyses", [])),
                report=results.get("final_report", ""),
                statistics=results.get("statistics", {}),
                detailed_analyses=results.get("detailed_analyses", []),
                duration=0,  # 如果原始代码有计时可以加上
                raw_data=results
            )
        else:
            return PatentAnalysisResult(
                report=f"未找到{gene_name}相关专利"
            )
class PatentAnalysisSystem:
    """专利分析系统主类"""
    
    def __init__(self, target_gene: str = None):
        # 智慧芽API配置
        self.base_url = "https://connect.zhihuiya.com"
        self.api_key = "fh10ixx8marmhm9kbl3cx5676qn8nshcuwtktz0b05ebl7qf"
        self.client_credentials = "74z26dxne81bnmrbd8vjwt7r8fc6tr6cxxdvapslbz4knycxknv3dnjprap6igjy"
        self.token = None
        self.session = requests.Session()
        
        # LLM配置
        self.llm_client = OpenAI(
            api_key='sk-9b3ad78d6d51431c90091b575072e62f',
            base_url="https://api.deepseek.com"
        )
        
        # 分析配置
        self.target_gene = target_gene or "GENE"  # 默认基因名
        self.initial_patents = 100
        self.top_patents = 1
        
    def set_target_gene(self, gene_name: str):
        """设置目标基因"""
        self.target_gene = gene_name
        self.log(f"目标基因设置为: {gene_name}", "INFO")
        
    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {"INFO": "blue", "SUCCESS": "green", "ERROR": "red", "WARN": "orange"}
        color = color_map.get(level, "blue")
        display(HTML(f'<span style="color:{color};">[{timestamp}] {level}: {message}</span>'))
    
    def llm_call(self, prompt: str) -> str:
        """调用LLM"""
        try:
            response = self.llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a professional patent analyst specializing in biotechnology and pharmaceutical patents."},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            self.log(f"LLM调用失败: {str(e)}", "ERROR")
            return ""

# %%
# ==================== Step 1: 智慧芽API接口 ====================

class ZhihuiyaAPI:
    """智慧芽API接口类"""
    
    def __init__(self, system: PatentAnalysisSystem):
        self.system = system
        
    def authenticate(self) -> bool:
        """获取访问token"""
        try:
            url = f"{self.system.base_url}/oauth/token"
            headers = {"content-type": "application/x-www-form-urlencoded"}
            data = f"grant_type=client_credentials&client_id={self.system.api_key}&client_secret={self.system.client_credentials}"
            
            response = self.system.session.post(url, data=data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") and "data" in result:
                self.system.token = result["data"]["token"]
                self.system.log("✅ Token获取成功", "SUCCESS")
                return True
            return False
        except Exception as e:
            self.system.log(f"认证失败: {str(e)}", "ERROR")
            return False
    
    def search_patents(self, query: str, limit: int = 100) -> List[Dict]:
        """P002 - 专利检索"""
        if not self.system.token and not self.authenticate():
            return []
        
        try:
            url = f"{self.system.base_url}/search/patent/query-search-patent/v2"
            headers = {
                "Content-Type": "application/json",
                "authorization": f"Bearer {self.system.token}"
            }
            params = {"apikey": self.system.api_key}
            
            payload = {
                "sort": [{"field": "SCORE", "order": "DESC"}],
                "limit": limit,
                "offset": 0,
                "query_text": query,
                "collapse_by": "PBD",
                "collapse_type": "ALL"
            }
            
            self.system.log(f"🔍 检索专利: {query} (限制{limit}件)")
            response = self.system.session.post(url, params=params, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") and "data" in result:
                patents = result["data"].get("results", [])
                self.system.log(f"✅ 找到 {len(patents)} 件专利", "SUCCESS")
                return patents
            return []
        except Exception as e:
            self.system.log(f"检索失败: {str(e)}", "ERROR")
            return []
    
    def get_simple_bibliography(self, patent_id: str, patent_number: str) -> Optional[Dict]:
        """P011 - 获取简要著录项目（含摘要）"""
        try:
            url = f"{self.system.base_url}/basic-patent-data/simple-bibliography"
            headers = {
                "Content-Type": "application/json",
                "authorization": f"Bearer {self.system.token}"
            }
            params = {
                "patent_id": patent_id,
                "patent_number": patent_number,
                "apikey": self.system.api_key
            }
            
            response = self.system.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") and result.get("data"):
                return result["data"][0] if isinstance(result["data"], list) else result["data"]
            return None
        except Exception as e:
            self.system.log(f"P011获取失败 {patent_number}: {str(e)}", "ERROR")
            return None
    
    def get_legal_status(self, patent_id: str, patent_number: str) -> Optional[Dict]:
        """获取法律状态"""
        try:
            url = f"{self.system.base_url}/basic-patent-data/legal-status"
            headers = {
                "Content-Type": "application/json",
                "authorization": f"Bearer {self.system.token}"
            }
            params = {
                "patent_id": patent_id,
                "patent_number": patent_number,
                "apikey": self.system.api_key
            }
            
            response = self.system.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            return result.get("data") if result.get("status") else None
        except Exception as e:
            self.system.log(f"法律状态获取失败: {str(e)}", "ERROR")
            return None
    
    def get_claims(self, patent_id: str, patent_number: str) -> Optional[str]:
        """获取权利要求书"""
        try:
            url = f"{self.system.base_url}/basic-patent-data/claim-data"
            headers = {
                "Content-Type": "application/json",
                "authorization": f"Bearer {self.system.token}"
            }
            params = {
                "patent_id": patent_id,
                "patent_number": patent_number,
                "apikey": self.system.api_key,
                "replace_by_related": "0"
            }
            
            response = self.system.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") and result.get("data"):
                claims_data = result["data"]
                if isinstance(claims_data, list) and claims_data:
                    claims = claims_data[0].get("claims", [])
                    claims_text = "\n\n".join([
                        f"Claim {c.get('claim_num', '')}: {c.get('claim_text', '')}"
                        for c in claims
                    ])
                    return claims_text
            return None
        except Exception as e:
            self.system.log(f"权利要求获取失败: {str(e)}", "ERROR")
            return None
    
    def get_description(self, patent_id: str, patent_number: str) -> Optional[str]:
        """获取说明书"""
        try:
            url = f"{self.system.base_url}/basic-patent-data/description-data"
            headers = {
                "Content-Type": "application/json",
                "authorization": f"Bearer {self.system.token}"
            }
            params = {
                "patent_id": patent_id,
                "patent_number": patent_number,
                "apikey": self.system.api_key,
                "replace_by_related": "0"
            }
            
            response = self.system.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") and result.get("data"):
                desc_data = result["data"]
                if isinstance(desc_data, list) and desc_data:
                    desc_text = desc_data[0].get("description", [{}])[0].get("text", "")
                    # 限制长度
                    if len(desc_text) > 50000:
                        desc_text = desc_text[:50000] + "\n...[内容已截断]"
                    return desc_text
            return None
        except Exception as e:
            self.system.log(f"说明书获取失败: {str(e)}", "ERROR")
            return None

# %%
# ==================== Step 2: 专利初步分析与筛选 ====================

class PatentScreener:
    """专利筛选与评分"""
    
    def __init__(self, system: PatentAnalysisSystem):
        self.system = system
        
    def process_initial_patents(self, patents: List[Dict]) -> pd.DataFrame:
        """处理初始专利数据"""
        processed = []
        
        for i, patent in enumerate(patents, 1):
            if i % 20 == 0:
                self.system.log(f"处理进度: {i}/{len(patents)}")
            
            # 提取基础信息
            patent_info = {
                "patent_id": patent.get("patent_id"),
                "patent_number": patent.get("pn"),
                "title": self._extract_title(patent),
                "assignee": patent.get("current_assignee", ""),
                "application_date": str(patent.get("apdt", "")),
                "publication_date": str(patent.get("pbdt", "")),
                "abstract": "",
                "legal_status": "",
                "score": patent.get("score", 0)
            }
            
            processed.append(patent_info)
            time.sleep(0.1)  # API限流
        
        return pd.DataFrame(processed)
    
    def _extract_title(self, patent: Dict) -> str:
        """提取标题"""
        title = patent.get("title", "")
        if isinstance(title, dict):
            title = title.get("en") or title.get("zh", "")
        return str(title)
    
    def enrich_with_abstracts(self, df: pd.DataFrame, api: ZhihuiyaAPI) -> pd.DataFrame:
        """补充摘要和法律状态"""
        self.system.log("📄 获取摘要和法律状态...")
        
        for idx, row in df.iterrows():
            if idx % 10 == 0:
                self.system.log(f"进度: {idx}/{len(df)}")
            
            # 获取摘要
            biblio = api.get_simple_bibliography(row["patent_id"], row["patent_number"])
            if biblio:
                abstracts = biblio.get("bibliographic_data", {}).get("abstracts", [])
                if abstracts:
                    # df.at[idx, "abstract"] = abstracts[0].get("text", "")[:500]
                    df.at[idx, "abstract"] = abstracts[0].get("text", "")[:10]

            
            # 获取法律状态
            legal = api.get_legal_status(row["patent_id"], row["patent_number"])
            if legal and isinstance(legal, list) and legal:
                legal_info = legal[0].get("patent_legal", {})
                status = legal_info.get("simple_legal_status", [])
                df.at[idx, "legal_status"] = ", ".join(status) if status else "Unknown"
            
            time.sleep(0.2)
        
        return df
    
    def analyze_patent_statistics(self, df: pd.DataFrame) -> Dict:
        """统计分析专利 - 通用版本"""
        stats = {
            "total_patents": len(df),
            "assignee_distribution": df["assignee"].value_counts().to_dict(),
            "year_distribution": df["application_date"].str[:4].value_counts().to_dict(),
            "legal_status_distribution": df["legal_status"].value_counts().to_dict()
        }
        
        # 基于基因名的动态技术类型识别
        tech_types = {
            "RNAi/siRNA": 0,
            "Antibody/mAb": 0,
            "Small Molecule": 0,
            "CRISPR/Gene Editing": 0,
            "Cell Therapy": 0,
            "Protein/Peptide": 0,
            "Gene Therapy": 0,
            "Other": 0
        }
        
        for _, row in df.iterrows():
            text = (str(row["title"]) + " " + str(row["abstract"])).lower()
            
            # 检测技术类型
            if any(kw in text for kw in ["rnai", "sirna", "interference", "oligonucleotide", "antisense"]):
                tech_types["RNAi/siRNA"] += 1
            elif any(kw in text for kw in ["antibody", "mab", "immunoglobulin", "monoclonal"]):
                tech_types["Antibody/mAb"] += 1
            elif any(kw in text for kw in ["compound", "inhibitor", "small molecule", "chemical"]):
                tech_types["Small Molecule"] += 1
            elif any(kw in text for kw in ["crispr", "cas9", "gene editing", "genome editing"]):
                tech_types["CRISPR/Gene Editing"] += 1
            elif any(kw in text for kw in ["car-t", "cell therapy", "tcr", "nk cell"]):
                tech_types["Cell Therapy"] += 1
            elif any(kw in text for kw in ["protein", "peptide", "fusion protein", "recombinant"]):
                tech_types["Protein/Peptide"] += 1
            elif any(kw in text for kw in ["gene therapy", "aav", "viral vector", "lentivirus"]):
                tech_types["Gene Therapy"] += 1
            else:
                tech_types["Other"] += 1
        
        stats["technology_distribution"] = tech_types
        
        return stats
    
    def score_and_rank_patents(self, df: pd.DataFrame) -> pd.DataFrame:
        """评分并排序专利 - 通用版本"""
        self.system.log("⚖️ 专利评分中...")
        
        # 构建与目标基因相关的关键词列表
        gene_lower = self.system.target_gene.lower()
        gene_keywords = [
            gene_lower,
            self.system.target_gene.upper(),
            # 添加常见的疾病相关关键词
            "therapeutic", "treatment", "inhibitor", "agonist", "antagonist",
            "disease", "disorder", "cancer", "tumor", "diabetes", "obesity",
            "inflammation", "metabolic", "cardiovascular", "neurological"
        ]
        
        # 顶级制药公司列表
        top_pharma_companies = [
            "ROCHE", "NOVARTIS", "PFIZER", "MERCK", "JOHNSON", "SANOFI", 
            "GLAXOSMITHKLINE", "GSK", "ASTRAZENECA", "ABBVIE", "BRISTOL",
            "LILLY", "AMGEN", "GILEAD", "REGENERON", "VERTEX", "BIOGEN",
            "ARROWHEAD", "ALNYLAM", "MODERNA", "BIONTECH", "WAVE"
        ]
        
        for idx, row in df.iterrows():
            score = 0
            
            # 1. 摘要和标题相关度（0-35分）
            text = (str(row["title"]) + " " + str(row["abstract"])).lower()
            
            # 基因名称出现得分
            gene_count = text.count(gene_lower)
            score += min(gene_count * 5, 20)
            
            # 其他关键词得分
            keyword_score = sum(2 for kw in gene_keywords[2:] if kw in text)
            score += min(keyword_score, 15)
            
            # 2. 申请人权重（0-20分）
            assignee = str(row["assignee"]).upper()
            if any(comp in assignee for comp in top_pharma_companies):
                score += 20
            elif assignee and "UNIVERSITY" in assignee:
                score += 10
            elif assignee:
                score += 5
            
            # 3. 时间新鲜度（0-15分）
            pub_date = str(row["publication_date"])
            if pub_date >= "20240000":
                score += 15
            elif pub_date >= "20230000":
                score += 12
            elif pub_date >= "20220000":
                score += 8
            elif pub_date >= "20200000":
                score += 5
            
            # 4. 法律状态（0-10分）
            legal = str(row["legal_status"]).lower()
            if "grant" in legal or "授权" in legal:
                score += 10
            elif "pending" in legal or "审查" in legal:
                score += 5
            
            # 5. 原始相关度分数（0-20分）
            original_score = row["score"]
            if original_score > 80:
                score += 20
            elif original_score > 60:
                score += 15
            elif original_score > 40:
                score += 10
            elif original_score > 20:
                score += 5
            
            df.at[idx, "final_score"] = score
        
        # 排序
        df_sorted = df.sort_values("final_score", ascending=False)
        
        return df_sorted

# %%
# ==================== Step 3: 深度分析Prompts ====================

class PatentAnalysisPrompts:
    """专利分析Prompt模板 - 通用版本"""
    
    def __init__(self, target_gene: str):
        self.target_gene = target_gene
    
    def description_analysis_prompt(self, description_text: str, patent_info: Dict) -> str:
        """说明书分析prompt"""
        return f"""
作为专利技术专家，请深度分析以下{self.target_gene}基因相关专利的说明书，并以连贯的段落形式输出分析结果。

专利号：{patent_info['patent_number']}
申请人：{patent_info['assignee']}
申请日：{patent_info['application_date']}

说明书内容：
{description_text}

请按以下结构分析（每部分用2-3个完整段落表述）：

## 1. 技术概述（2段）
第一段：简要描述这是什么类型的技术（RNAi/抗体/小分子/基因编辑/细胞治疗等），针对{self.target_gene}靶点要解决什么具体问题。
第二段：说明核心创新点是什么，与现有技术相比的主要改进在哪里。

## 2. 技术方案分析（3段）
第一段：详细描述具体的技术方案。根据技术类型分析关键要素（序列设计、化合物结构、载体构建等）。
第二段：分析优化或改进策略（化学修饰、结构优化、递送系统等）。
第三段：与同领域其他专利技术的对比，突出本专利的独特性。

## 3. 实验验证（3段）
第一段：概述实验设计的整体思路，包括体外、体内实验的层次安排。
第二段：详细描述最关键的实验结果，包括具体数据（IC50、EC50、抑制率、持续时间等）。
第三段：安全性评估和临床转化考虑。如果有临床试验设计，说明主要终点和给药方案。

## 4. 商业价值评估（2段）
第一段：评估{self.target_gene}相关疾病的市场规模和竞争格局。该技术的目标适应症是什么？市场潜力如何？
第二段：分析专利技术的可实施性和商业化前景。生产工艺是否成熟？成本是否可控？临床开发路径是否清晰？

## 5. 关键技术参数提取
请特别提取以下关键信息（如果存在）：
- 核心序列/化合物：具体序列号或化学结构
- 靶向机制：{self.target_gene}的作用位点或机制
- 实验数据：关键的量化指标
- 技术特征：独特的技术特点
- 临床方案：剂量、给药途径、频率（如有）

输出要求：
- 使用完整流畅的段落，避免碎片化列表
- 数据自然融入叙述中
- 保持专业但易读的文风
- 总字数控制在1000-1500字
"""
    
    def claims_analysis_prompt(self, claims_text: str, patent_info: Dict) -> str:
        """权利要求分析prompt"""
        return f"""
作为专利法律专家，请分析以下{self.target_gene}基因相关专利的权利要求书，并以适合专业报告的段落形式输出。

专利号：{patent_info['patent_number']}
申请人：{patent_info['assignee']}

权利要求书：
{claims_text}

请按以下结构分析（每部分用2-3个完整段落表述）：

## 1. 权利要求架构概述（2段）
第一段：描述权利要求的整体结构，包括权利要求数量、独立权利要求的类型分布。
第二段：分析权利要求之间的逻辑关系和保护策略。

## 2. 核心保护范围分析（3段）
第一段：深入分析独立权利要求的保护范围，特别是与{self.target_gene}相关的必要技术特征。
第二段：分析关键限定条件对保护范围的影响。
第三段：评估其他独立权利要求的补充作用。

## 3. 技术特征递进策略（2段）
第一段：分析从属权利要求的递进逻辑和层次结构。
第二段：评价关键从属权利要求的价值和商业意义。

## 4. 法律稳定性与侵权分析（2段）
第一段：评估权利要求的法律稳定性（清楚性、支持性、创造性）。
第二段：分析侵权判定的关键要素和潜在规避路径。

## 5. 与其他{self.target_gene}专利的关系（1段）
分析该专利权利要求与其他主要申请人{self.target_gene}专利的潜在冲突或互补关系。

输出要求：
- 使用连贯的专业段落
- 法律分析结合商业考虑
- 总字数控制在800-1200字
"""
    
    def final_report_prompt(self, statistics: Dict, detailed_analyses: List[Dict]) -> str:
        """最终综合报告prompt"""
        return f"""
你是专业的专利分析师，请基于以下数据撰写一份详细的{self.target_gene}基因相关专利技术综述报告。

【100篇专利统计数据】
{json.dumps(statistics, ensure_ascii=False, indent=2)}

【10篇核心专利详细分析】
{json.dumps(detailed_analyses, ensure_ascii=False, indent=2)}

请生成一份专业的专利技术综述报告，格式如下：

# {self.target_gene}基因相关全球专利竞争格局分析

## 一、专利数量、类型与地域分布

### 全球专利公开数量与类型（400字）
基于分析的100篇{self.target_gene}相关专利，详细说明：
- 专利总数和时间分布趋势
- 技术类型分布（各类技术占比）
- 主要申请人分布
- 法律状态统计

### 地域分布（300字）
分析专利的地域布局特点。

## 二、核心专利权利人及布局策略

基于10篇核心专利的深度分析，详细描述各主要玩家的技术策略。
[根据实际申请人情况动态生成各公司分析]

## 三、技术发展趋势与关键创新

### 技术路线对比（500字）
详细对比不同公司针对{self.target_gene}的技术方案差异。

### 关键技术参数汇总
整理所有核心专利的关键参数。

## 四、专利保护范围与法律风险

### 权利要求保护范围对比（400字）
对比不同专利的保护策略。

### 潜在冲突分析（300字）
识别可能的专利冲突点。

## 五、商业机会与投资建议

### 技术空白与机会（300字）
基于专利分析识别的{self.target_gene}领域机会。

### 投资与研发建议（300字）
- 最有前景的技术路线
- 需要规避的专利壁垒
- 潜在的合作机会

## 六、结论与展望

总结{self.target_gene}专利领域的发展现状和未来趋势（300字）。

【输出要求】
1. 必须基于提供的数据，不要编造信息
2. 包含具体的专利号、申请人、技术细节
3. 数据和分析要相互印证
4. 保持客观专业的语气
5. 总字数3000-4000字
"""

# %%
# ==================== Step 4: 主流程执行 ====================

class PatentAnalysisPipeline:
    """专利分析主流程 - 通用版本"""
    
    def __init__(self, target_gene: str = None):
        self.target_gene = target_gene
        self.system = PatentAnalysisSystem(target_gene)
        self.api = ZhihuiyaAPI(self.system)
        self.screener = PatentScreener(self.system)
        self.prompts = None  # 将在运行时初始化
        
    def run_complete_analysis(self, target_gene: str = None) -> Dict:
        """运行完整分析流程
        
        Args:
            target_gene: 目标基因名称（如 "PCSK9", "PD-1", "EGFR" 等）
        
        Returns:
            包含统计数据、详细分析和最终报告的字典
        """
        
        # 设置目标基因
        if target_gene:
            self.target_gene = target_gene
            self.system.set_target_gene(target_gene)
        elif not self.target_gene:
            raise ValueError("请提供目标基因名称")
        
        # 初始化Prompts
        self.prompts = PatentAnalysisPrompts(self.target_gene)
        
        # ========== Step 1: 获取专利数据 ==========
        self.system.log("=" * 50)
        self.system.log(f"🚀 Step 1: 获取{self.target_gene}相关专利数据", "INFO")
        
        # 1.1 搜索专利
        # search_results = self.api.search_patents(self.target_gene, limit=500)
        search_results = self.api.search_patents(self.target_gene, limit=10)

        if not search_results:
            self.system.log(f"未找到{self.target_gene}相关专利", "ERROR")
            return {}
        
        # 1.2 处理基础数据
        df_patents = self.screener.process_initial_patents(search_results)
        self.system.log(f"✅ 处理了 {len(df_patents)} 篇专利", "SUCCESS")
        
        # ========== Step 2: 获取摘要和统计分析 ==========
        self.system.log("=" * 50)
        self.system.log("🔍 Step 2: 获取摘要并进行统计分析", "INFO")
        
        # 2.1 补充摘要和法律状态
        df_patents = self.screener.enrich_with_abstracts(df_patents, self.api)
        
        # 2.2 统计分析
        statistics = self.screener.analyze_patent_statistics(df_patents)
        statistics["target_gene"] = self.target_gene
        self.system.log("📊 专利统计分析完成", "SUCCESS")
        
        # 显示统计结果
        print(f"\n{self.target_gene}相关技术类型分布:")
        for tech, count in statistics["technology_distribution"].items():
            print(f"  {tech}: {count}件")
        
        print(f"\n{self.target_gene}专利主要申请人（前5）:")
        assignee_dist = dict(list(statistics["assignee_distribution"].items())[:5])
        for assignee, count in assignee_dist.items():
            print(f"  {assignee}: {count}件")
        
        # 2.3 评分和排序
        df_patents = self.screener.score_and_rank_patents(df_patents)
        
        # ========== Step 3: 选择Top 10专利 ==========
        self.system.log("=" * 50)
        self.system.log("🎯 Step 3: 选择Top 10专利进行深度分析", "INFO")
        
        top10_patents = df_patents.head(1)
        
        # 显示Top 10
        print(f"\n{self.target_gene}相关Top 10专利:")
        for idx, row in top10_patents.iterrows():
            print(f"{idx+1}. {row['patent_number']} - {row['assignee'][:30]} (Score: {row['final_score']})")
        
        # ========== Step 4: 深度分析Top 10专利 ==========
        self.system.log("=" * 50)
        self.system.log("🔬 Step 4: 深度分析核心专利", "INFO")
        
        detailed_analyses = []
        
        for idx, patent in top10_patents.iterrows():
            self.system.log(f"分析专利 {idx+1}/10: {patent['patent_number']}")
            
            # 4.1 获取说明书
            description = self.api.get_description(patent["patent_id"], patent["patent_number"])
            
            # 4.2 获取权利要求
            claims = self.api.get_claims(patent["patent_id"], patent["patent_number"])
            
            if description and claims:
                # 4.3 LLM分析说明书
                desc_prompt = self.prompts.description_analysis_prompt(description, patent.to_dict())
                desc_analysis = self.system.llm_call(desc_prompt)
                
                # 4.4 LLM分析权利要求
                claims_prompt = self.prompts.claims_analysis_prompt(claims, patent.to_dict())
                claims_analysis = self.system.llm_call(claims_prompt)
                
                detailed_analyses.append({
                    "patent_number": patent["patent_number"],
                    "assignee": patent["assignee"],
                    "application_date": patent["application_date"],
                    "title": patent["title"],
                    "technical_analysis": desc_analysis,
                    "legal_analysis": claims_analysis
                })
                
                self.system.log(f"✅ 完成分析: {patent['patent_number']}", "SUCCESS")
            else:
                self.system.log(f"⚠️ 无法获取完整内容: {patent['patent_number']}", "WARN")
            
            time.sleep(2)  # API限流
        
        # ========== Step 5: 生成综合报告 ==========
        self.system.log("=" * 50)
        self.system.log("📝 Step 5: 生成综合报告", "INFO")
        
        # 5.1 准备数据
        statistics["top_patents"] = top10_patents[["patent_number", "assignee", "final_score"]].to_dict("records")
        
        # 5.2 生成最终报告
        final_prompt = self.prompts.final_report_prompt(statistics, detailed_analyses)
        final_report = self.system.llm_call(final_prompt)
        
        # ========== 保存结果 ==========
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存详细分析
        # with open(f"patent_detailed_analysis_{self.target_gene}_{timestamp}.json", "w", encoding="utf-8") as f:
        #     json.dump({
        #         "target_gene": self.target_gene,
        #         "statistics": statistics,
        #         "detailed_analyses": detailed_analyses
        #     }, f, ensure_ascii=False, indent=2)
        
        # # 保存最终报告
        # with open(f"patent_report_{self.target_gene}_{timestamp}.md", "w", encoding="utf-8") as f:
        #     f.write(final_report)
        
        # self.system.log(f"✅ {self.target_gene}专利分析完成！报告已保存", "SUCCESS")
        
        return {
            "target_gene": self.target_gene,
            "statistics": statistics,
            "detailed_analyses": detailed_analyses,
            "final_report": final_report
        }

