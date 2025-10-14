# agent_core/agents/tools/retrievers/real_patent_retriever.py
# 真实专利数据检索器 - 集成多个可用的专利API

import asyncio
import aiohttp
import requests
import json
import logging
import time
import re
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import urllib.parse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 专利API配置
PATENT_API_CONFIG = {
    'uspto': {
        'enabled': True,
        'api_key': os.getenv('USPTO_API_KEY'),
        'rate_limit': 100,  # 每分钟请求数
        'base_url': 'https://developer.uspto.gov/ibd-api/v1'
    },
    'patentsview': {
        'enabled': True,
        'api_key': os.getenv('PATENTSVIEW_API_KEY'),  # 新API需要密钥
        'rate_limit': 45,  # 每分钟请求数
        'base_url': 'https://search.patentsview.org/api/v1/patent'  # 新API端点
    },
    'google': {
        'enabled': True,
        'use_proxy': False,
        'base_url': 'https://patents.google.com'
    },
    'wipo': {
        'enabled': True,
        'session_timeout': 3600,
        'base_url': 'https://patentscope.wipo.int'
    }
}

@dataclass
class Patent:
    """统一的专利数据结构"""
    patent_id: str          # 专利号
    title: str              # 标题
    abstract: str           # 摘要
    assignee: str           # 申请人/受让人
    inventors: List[str]    # 发明人列表
    filing_date: str        # 申请日期
    publication_date: str   # 公开日期
    classifications: List[str]  # 分类号
    status: str             # 状态
    url: str                # 专利链接
    source: str             # 数据来源 (Google/USPTO/PatentsView/WIPO)
    relevance_score: float  # 相关性评分
    
    def __post_init__(self):
        if self.inventors is None:
            self.inventors = []
        if self.classifications is None:
            self.classifications = []
        if not self.url and self.patent_id:
            self.url = f"https://patents.google.com/patent/{self.patent_id}"

@dataclass
class PatentSearchResult:
    """专利搜索结果"""
    query: str
    total_count: int
    retrieved_count: int
    patents: List[Patent]
    search_timestamp: str
    sources_used: List[str]
    api_version: str = "3.0.0"

class PatentsViewRetriever:
    """PatentsView API检索器（新版API，需要API密钥）"""
    
    def __init__(self):
        self.base_url = PATENT_API_CONFIG['patentsview']['base_url']
        self.api_key = PATENT_API_CONFIG['patentsview']['api_key']
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_count = 0
        self.last_request_time = 0
        
    async def __aenter__(self):
        headers = {
            'User-Agent': 'PatentAnalyzer/3.0',
            'Accept': 'application/json'
        }
        
        # 添加API密钥（如果有的话）
        if self.api_key:
            headers['X-Api-Key'] = self.api_key
            
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=headers
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_patents(self, query: str, max_results: int = 20) -> List[Patent]:
        """使用PatentsView新API搜索专利"""
        try:
            if not self.api_key:
                logger.warning("PatentsView API Key未配置，跳过PatentsView搜索")
                return []
                
            # 速率限制控制
            await self._rate_limit()
            
            logger.info(f"PatentsView新API搜索: {query}")
            
            # 构建查询参数 - 新API格式
            params = {
                "q": json.dumps({
                    "_text_any": {
                        "patent_title": query
                    }
                }),
                "f": json.dumps([
                    "patent_id",
                    "patent_title", 
                    "patent_abstract",
                    "patent_date",
                    "assignee_organization",
                    "inventor_name_first",
                    "inventor_name_last",
                    "cpc_section_id"
                ]),
                "o": json.dumps({
                    "per_page": min(max_results, 25)
                })
            }
            
            # 使用GET请求（新API推荐）
            async with self.session.get(
                self.base_url,
                params=params
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    patents = self._parse_patentsview_response(data, query)
                    logger.info(f"PatentsView新API获取到 {len(patents)} 个结果")
                    return patents
                elif response.status == 401:
                    logger.error("PatentsView API认证失败，请检查API密钥")
                    return []
                elif response.status == 429:
                    logger.warning("PatentsView API请求限制，请稍后重试")
                    return []
                else:
                    logger.warning(f"PatentsView新API请求失败: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"PatentsView搜索失败: {e}")
            return []
    
    def _parse_patentsview_response(self, data: Dict, query: str) -> List[Patent]:
        """解析PatentsView新API响应"""
        patents = []
        
        try:
            # 新API响应格式可能不同，尝试多种格式
            patents_data = data.get('patents', []) or data.get('results', []) or data.get('data', [])
            
            for item in patents_data:
                # 处理发明人
                inventors = []
                if 'inventors' in item:
                    for inv in item['inventors']:
                        first_name = inv.get('inventor_name_first', '')
                        last_name = inv.get('inventor_name_last', '')
                        if first_name or last_name:
                            inventors.append(f"{first_name} {last_name}".strip())
                
                # 处理受让人
                assignees = item.get('assignees', [])
                assignee = assignees[0].get('assignee_organization', 'Unknown') if assignees else 'Unknown'
                
                # 处理分类
                classifications = []
                if 'cpcs' in item:
                    for cpc in item['cpcs']:
                        if 'cpc_section_id' in cpc:
                            classifications.append(cpc['cpc_section_id'])
                
                patent = Patent(
                    patent_id=item.get('patent_number', ''),
                    title=item.get('patent_title', ''),
                    abstract=item.get('patent_abstract', '')[:500],  # 限制长度
                    assignee=assignee,
                    inventors=inventors,
                    filing_date=item.get('patent_date', ''),
                    publication_date=item.get('patent_date', ''),
                    classifications=classifications,
                    status='Published',
                    url=f"https://patents.google.com/patent/{item.get('patent_number', '')}",
                    source='patentsview',
                    relevance_score=self._calculate_relevance(item, query)
                )
                patents.append(patent)
                
        except Exception as e:
            logger.error(f"解析PatentsView响应失败: {e}")
            
        return patents
    
    def _calculate_relevance(self, patent_data: Dict, query: str) -> float:
        """计算专利相关性评分"""
        score = 0.5  # 基础分数
        
        title = patent_data.get('patent_title', '').lower()
        abstract = patent_data.get('patent_abstract', '').lower()
        query_lower = query.lower()
        
        # 标题匹配加分
        if query_lower in title:
            score += 0.3
            
        # 摘要匹配加分
        if query_lower in abstract:
            score += 0.2
            
        return min(score, 1.0)
    
    async def _rate_limit(self):
        """速率限制控制"""
        current_time = time.time()
        if current_time - self.last_request_time < 60/PATENT_API_CONFIG['patentsview']['rate_limit']:
            await asyncio.sleep(60/PATENT_API_CONFIG['patentsview']['rate_limit'])
        self.last_request_time = current_time

class GooglePatentsRetriever:
    """Google Patents检索器 - 使用Google搜索方法"""
    
    def __init__(self):
        self.base_url = PATENT_API_CONFIG['google']['base_url']
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_patents(self, query: str, max_results: int = 20) -> List[Patent]:
        """使用Google搜索查找Google Patents中的专利（使用requests同步方法）"""
        try:
            logger.info(f"Google Patents搜索（通过Google搜索）: {query}")
            
            # 使用同步方法（已验证成功）
            patents = await asyncio.to_thread(self._search_patents_sync, query, max_results)
            
            logger.info(f"Google Patents获取到 {len(patents)} 个结果")
            return patents
                    
        except Exception as e:
            logger.error(f"Google Patents搜索失败: {e}")
            return []
    
    def _search_patents_sync(self, query: str, max_results: int) -> List[Patent]:
        """同步方法搜索专利（基于验证成功的代码）"""
        # 使用成功验证的搜索词组合
        search_terms = [
            f"{query} patent site:patents.google.com",
            f"{query} gene patent site:patents.google.com",
            f"{query} therapeutic patent site:patents.google.com"
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        all_patents = []
        
        for search_term in search_terms:
            try:
                google_url = f"https://www.google.com/search?q={urllib.parse.quote(search_term)}&num={min(max_results, 10)}"
                
                response = requests.get(google_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    patents = self._parse_google_search_results_sync(response.text, query)
                    all_patents.extend(patents)
                    
                    # 如果找到了足够的专利，就停止搜索
                    if len(all_patents) >= max_results:
                        break
                else:
                    logger.warning(f"Google搜索请求失败: {response.status_code}")
                
                # 限制请求频率
                time.sleep(2)
                
            except Exception as e:
                logger.warning(f"搜索词 '{search_term}' 失败: {e}")
                continue
        
        # 去重
        unique_patents = {}
        for patent in all_patents:
            pid = patent['patent_id']
            if pid not in unique_patents:
                unique_patents[pid] = patent
        
        patents_list = list(unique_patents.values())[:max_results]
        
        # 获取专利详细信息
        enhanced_patents = []
        for patent in patents_list:
            try:
                details = self._get_patent_details_sync(patent['url'])
                # 合并基本信息和详细信息
                enhanced_patent = {**patent, **details}
                enhanced_patents.append(self._create_patent_object(enhanced_patent, query))
                # 限制请求频率
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"获取专利详情失败: {e}")
                # 使用基本信息创建专利对象
                enhanced_patents.append(self._create_patent_object(patent, query))
        
        return enhanced_patents
    
    def _parse_google_search_results_sync(self, html_content: str, query: str) -> List[Dict]:
        """解析Google搜索结果中的专利链接（同步版本）"""
        patents = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Google搜索结果的常见选择器
            result_selectors = [
                'div.g a[href*="patents.google.com/patent/"]',
                'a[href*="patents.google.com/patent/"]',
                'h3 a[href*="patents.google.com/patent/"]'
            ]
            
            for selector in result_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    if 'patents.google.com/patent/' in href:
                        # 清理URL（移除Google的重定向）
                        if href.startswith('/url?q='):
                            href = href.split('/url?q=')[1].split('&')[0]
                        
                        # 提取专利号
                        patent_match = re.search(r'/patent/([^/?&]+)', href)
                        if patent_match:
                            patent_id = patent_match.group(1)
                            title = link.get_text(strip=True)
                            
                            patent_info = {
                                'patent_id': patent_id,
                                'title': title,
                                'url': href,
                                'source': 'google_search'
                            }
                            patents.append(patent_info)
            
            # 去重
            unique_patents = {}
            for patent in patents:
                pid = patent['patent_id']
                if pid not in unique_patents:
                    unique_patents[pid] = patent
            
            return list(unique_patents.values())
            
        except Exception as e:
            logger.error(f"解析Google搜索结果失败（同步）: {e}")
            return []
    
    def _get_patent_details_sync(self, patent_url: str) -> Dict:
        """获取专利详细信息（同步版本）"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(patent_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                details = {}
                
                # 查找标题
                title_selectors = ['h1', 'title', '.patent-title']
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        details['title'] = title_elem.get_text(strip=True)
                        break
                
                # 查找申请人
                assignee_selectors = [
                    '[data-patent-assignee]',
                    '.assignee',
                    '[class*="assignee"]'
                ]
                for selector in assignee_selectors:
                    assignee_elem = soup.select_one(selector)
                    if assignee_elem:
                        details['assignee'] = assignee_elem.get_text(strip=True)
                        break
                
                # 查找摘要
                abstract_selectors = [
                    '.abstract',
                    '[data-patent-abstract]',
                    '.patent-abstract'
                ]
                for selector in abstract_selectors:
                    abstract_elem = soup.select_one(selector)
                    if abstract_elem:
                        details['abstract'] = abstract_elem.get_text(strip=True)[:500]
                        break
                
                return details
                
        except Exception as e:
            logger.warning(f"获取专利详情失败（同步）: {e}")
        
        return {}
    
    def _create_patent_object(self, patent_data: Dict, query: str) -> Patent:
        """创建Patent对象"""
        return Patent(
            patent_id=patent_data.get('patent_id', 'Unknown'),
            title=patent_data.get('title', f'Patent related to {query}')[:200],
            abstract=patent_data.get('abstract', 'Abstract not available')[:500],
            assignee=patent_data.get('assignee', 'Unknown'),
            inventors=['Unknown'],
            filing_date='Unknown',
            publication_date='Unknown',
            classifications=['Unknown'],
            status='Published',
            url=patent_data.get('url', ''),
            source='google_patents_search',
            relevance_score=0.9 if query.lower() in patent_data.get('title', '').lower() else 0.7
        )

class USPTOAPIRetriever:
    """USPTO官方API检索器"""
    
    def __init__(self):
        self.base_url = PATENT_API_CONFIG['uspto']['base_url']
        self.api_key = PATENT_API_CONFIG['uspto']['api_key']
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        headers = {
            'User-Agent': 'PatentAnalyzer/3.0',
            'Accept': 'application/json'
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=headers
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_patents(self, query: str, max_results: int = 20) -> List[Patent]:
        """使用USPTO API搜索专利"""
        try:
            if not self.api_key:
                logger.warning("USPTO API Key未配置，跳过USPTO搜索")
                return []
                
            logger.info(f"USPTO API搜索: {query}")
            
            # USPTO API查询参数
            params = {
                'searchText': query,
                'rows': min(max_results, 100),
                'start': 0
            }
            
            search_url = f"{self.base_url}/patent/application"
            
            async with self.session.get(search_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    patents = self._parse_uspto_response(data, query)
                    logger.info(f"USPTO API获取到 {len(patents)} 个结果")
                    return patents
                else:
                    logger.warning(f"USPTO API请求失败: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"USPTO API搜索失败: {e}")
            return []
    
    def _parse_uspto_response(self, data: Dict, query: str) -> List[Patent]:
        """解析USPTO API响应"""
        patents = []
        
        try:
            results = data.get('results', [])
            
            for item in results:
                patent = Patent(
                    patent_id=item.get('patentNumber', ''),
                    title=item.get('title', ''),
                    abstract=item.get('abstract', '')[:300],
                    assignee=item.get('assignee', 'Unknown'),
                    inventors=item.get('inventors', ['Unknown']),
                    filing_date=item.get('filingDate', ''),
                    publication_date=item.get('publicationDate', ''),
                    classifications=item.get('classifications', []),
                    status=item.get('status', 'Published'),
                    url=f"https://patents.uspto.gov/patent/{item.get('patentNumber', '')}",
                    source='uspto_api',
                    relevance_score=0.9
                )
                patents.append(patent)
                
        except Exception as e:
            logger.error(f"解析USPTO响应失败: {e}")
            
        return patents

class WIPOPatentScopeRetriever:
    """WIPO PatentScope API检索器"""
    
    def __init__(self):
        self.base_url = PATENT_API_CONFIG['wipo']['base_url']
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'PatentAnalyzer/3.0',
                'Accept': 'application/json'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_patents(self, query: str, max_results: int = 20) -> List[Patent]:
        """使用WIPO PatentScope搜索专利"""
        try:
            logger.info(f"WIPO PatentScope搜索: {query}")
            
            # WIPO搜索参数
            search_url = f"{self.base_url}/search/en/search.jsf"
            params = {
                'query': query,
                'maxRec': min(max_results, 50)
            }
            
            async with self.session.get(search_url, params=params) as response:
                if response.status == 200:
                    html_content = await response.text()
                    patents = self._parse_wipo_html(html_content, query)
                    logger.info(f"WIPO获取到 {len(patents)} 个结果")
                    return patents
                else:
                    logger.warning(f"WIPO请求失败: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"WIPO搜索失败: {e}")
            return []
    
    def _parse_wipo_html(self, html_content: str, query: str) -> List[Patent]:
        """解析WIPO HTML响应 - 仅返回真实解析的数据"""
        patents = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # WIPO结果解析 - 需要根据实际HTML结构调整
            # 目前WIPO网站结构复杂，需要进一步分析
            result_items = soup.find_all('div', class_='result-item') 
            
            if not result_items:
                # 尝试其他可能的选择器
                result_items = soup.find_all('tr', class_='search-result')
                
            if not result_items:
                logger.warning(f"WIPO: 未找到匹配的HTML结构，无法解析专利结果")
                return []
            
            for item in result_items[:10]:
                try:
                    # 尝试提取真实的专利信息
                    title_elem = item.find('a') or item.find('span', class_='title')
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    
                    # 提取专利ID
                    patent_id = "Unknown"
                    id_elem = item.find('span', class_='patent-id') or item.find('td', class_='patent-number')
                    if id_elem:
                        patent_id = id_elem.get_text(strip=True)
                    
                    # 只添加有有效标题的真实专利
                    if title and title != query:  # 避免重复查询词
                        patent = Patent(
                            patent_id=patent_id,
                            title=title,
                            abstract="Abstract requires full patent access",
                            assignee="Unknown",
                            inventors=['Unknown'],
                            filing_date="Unknown",
                            publication_date="Unknown",
                            classifications=['Unknown'],
                            status='Published',
                            url=f"{self.base_url}/search",
                            source='wipo',
                            relevance_score=0.6
                        )
                        patents.append(patent)
                        
                except Exception as e:
                    logger.warning(f"解析WIPO单个结果失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析WIPO HTML失败: {e}")
            
        logger.info(f"WIPO解析完成: 从HTML中提取到 {len(patents)} 个真实专利")
        return patents

class UnifiedPatentRetriever:
    """统一的专利检索器，聚合多个数据源"""
    
    def __init__(self):
        self.retrievers = {
            'patentsview': PatentsViewRetriever(),
            'google': GooglePatentsRetriever(),
            'uspto': USPTOAPIRetriever(),
            'wipo': WIPOPatentScopeRetriever()
        }
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def search_patents(self, 
                           query: str, 
                           sources: List[str] = None, 
                           max_results: int = 20) -> PatentSearchResult:
        """
        从多个源并发搜索，去重并排序
        优先级：Google搜索 > PatentsView > USPTO > WIPO
        """
        search_timestamp = datetime.now().isoformat()
        
        if sources is None:
            sources = ['google', 'patentsview']  # 优先使用Google搜索方法
            
        # 过滤掉未启用的源
        enabled_sources = [s for s in sources if PATENT_API_CONFIG.get(s, {}).get('enabled', False)]
        
        if not enabled_sources:
            error_msg = f"没有启用的专利数据源。请配置至少一个API密钥：{list(PATENT_API_CONFIG.keys())}"
            logger.error(error_msg)
            return PatentSearchResult(
                query=query,
                total_count=0,
                retrieved_count=0,
                patents=[],
                search_timestamp=search_timestamp,
                sources_used=[],
                api_version="ERROR: " + error_msg
            )
        
        try:
            logger.info(f"统一专利搜索开始: {query} (启用源: {enabled_sources})")
            
            all_patents = []
            sources_used = []
            api_errors = []
            results_per_source = max(5, max_results // len(enabled_sources))
            
            # 记录每个API的调用状态
            api_status = {}
            for source in enabled_sources:
                config = PATENT_API_CONFIG.get(source, {})
                has_key = bool(config.get('api_key'))
                api_status[source] = {
                    'enabled': config.get('enabled', False),
                    'has_api_key': has_key,
                    'base_url': config.get('base_url', 'N/A')
                }
                key_status = '已配置' if has_key else ('不需要' if source in ['google', 'wipo'] else '未配置')
                logger.info(f"API状态 - {source}: 启用={config.get('enabled', False)}, 密钥={key_status}")
            
            # 并发搜索所有启用的源
            search_tasks = []
            for source in enabled_sources:
                if source in self.retrievers:
                    retriever = self.retrievers[source] 
                    task = self._search_with_source(retriever, query, results_per_source, source)
                    search_tasks.append(task)
            
            # 等待所有搜索完成
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # 处理搜索结果
            for i, result in enumerate(search_results):
                source_name = enabled_sources[i]
                if isinstance(result, Exception):
                    error_msg = f"源 {source_name} 搜索失败: {result}"
                    logger.error(error_msg)
                    api_errors.append(error_msg)
                else:
                    patents, source_name = result
                    if patents:
                        all_patents.extend(patents)
                        sources_used.append(source_name)
                        logger.info(f"✅ {source_name} 成功获取到 {len(patents)} 个真实专利")
                    else:
                        logger.warning(f"⚠️ {source_name} 搜索完成但未返回专利数据")
            
            # 如果所有数据源都失败
            if not all_patents and api_errors:
                error_summary = f"所有专利数据源均失败: {'; '.join(api_errors)}"
                logger.error(error_summary)
                return PatentSearchResult(
                    query=query,
                    total_count=0,
                    retrieved_count=0,
                    patents=[],
                    search_timestamp=search_timestamp,
                    sources_used=[],
                    api_version="ERROR: " + error_summary
                )
            
            # 去重并排序
            unique_patents = self._deduplicate_and_rank_patents(all_patents, query)
            final_patents = unique_patents[:max_results]
            
            success_msg = f"统一专利搜索完成: {len(final_patents)} 件真实专利，来源: {sources_used}"
            logger.info(success_msg)
            
            return PatentSearchResult(
                query=query,
                total_count=len(final_patents),
                retrieved_count=len(final_patents),
                patents=final_patents,
                search_timestamp=search_timestamp,
                sources_used=sources_used
            )
            
        except Exception as e:
            error_msg = f"统一专利搜索系统错误: {e}"
            logger.error(error_msg)
            return PatentSearchResult(
                query=query,
                total_count=0,
                retrieved_count=0,
                patents=[],
                search_timestamp=search_timestamp,
                sources_used=[],
                api_version="SYSTEM_ERROR: " + error_msg
            )
    
    async def _search_with_source(self, retriever, query: str, max_results: int, source_name: str):
        """使用指定源搜索专利"""
        try:
            async with retriever as r:
                patents = await r.search_patents(query, max_results)
                return patents, source_name
        except Exception as e:
            logger.error(f"{source_name} 搜索失败: {e}")
            return [], source_name
    
    def _deduplicate_and_rank_patents(self, patents: List[Patent], query: str) -> List[Patent]:
        """去重并按相关性排序专利"""
        if not patents:
            return []
        
        # 去重：基于专利ID和标题相似性
        seen_ids = set()
        seen_titles = set()
        unique_patents = []
        
        for patent in patents:
            # 基于专利ID去重
            if patent.patent_id and patent.patent_id in seen_ids:
                continue
                
            # 基于标题相似性去重
            title_key = patent.title[:60].lower().strip()
            if title_key and title_key in seen_titles:
                continue
            
            if patent.patent_id:
                seen_ids.add(patent.patent_id)
            if title_key:
                seen_titles.add(title_key)
                
            unique_patents.append(patent)
        
        # 按相关性和数据源优先级排序
        def sort_key(patent: Patent) -> tuple:
            # 数据源优先级
            source_priority = {
                'google_patents_search': 1,  # 最高优先级
                'google_patents': 2,
                'patentsview': 3,
                'uspto_api': 4, 
                'wipo': 5
            }
            
            return (
                -patent.relevance_score,  # 相关性评分（降序）
                source_priority.get(patent.source, 5),  # 数据源优先级
                patent.patent_id  # 专利ID（用于稳定排序）
            )
        
        unique_patents.sort(key=sort_key)
        return unique_patents
    
    async def search_by_gene(self, 
                           gene: str, 
                           additional_terms: List[str] = None,
                           max_results: int = 20,
                           focus_areas: List[str] = None) -> PatentSearchResult:
        """按基因名称搜索相关专利"""
        
        # 构建搜索查询
        query_parts = [gene]
        
        if additional_terms:
            query_parts.extend(additional_terms[:2])
        
        if focus_areas:
            for area in focus_areas[:2]:
                if area.lower() in ['therapy', 'treatment']:
                    query_parts.append('treatment')
                elif area.lower() == 'diagnostic':
                    query_parts.append('diagnostic')
                elif area.lower() == 'crispr':
                    query_parts.append('CRISPR')
        
        # 构建最终查询
        query = ' '.join(query_parts[:4])  # 限制查询复杂度
        
        return await self.search_patents(query, max_results=max_results)

# 测试函数
async def test_real_patent_apis():
    """测试真实专利API"""
    print("🔍 测试真实专利API")
    print("=" * 50)
    
    async with UnifiedPatentRetriever() as retriever:
        # 测试基因搜索
        print("\n1. 测试PCSK9基因专利搜索:")
        result = await retriever.search_by_gene(
            "PCSK9", 
            additional_terms=["cholesterol"],
            max_results=10
        )
        
        print(f"✅ 搜索完成: {result.retrieved_count} 个专利")
        print(f"数据源: {', '.join(result.sources_used)}")
        
        for i, patent in enumerate(result.patents[:3], 1):
            print(f"\n专利 {i}:")
            print(f"  ID: {patent.patent_id}")
            print(f"  标题: {patent.title[:80]}...")
            print(f"  来源: {patent.source}")
            print(f"  相关性: {patent.relevance_score:.2f}")

if __name__ == "__main__":
    asyncio.run(test_real_patent_apis())