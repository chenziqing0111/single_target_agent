# agent_core/tools/web_scraper.py
# Web search and scraping tool, supports Exa API

import os
import logging
from typing import List, Dict, Any, Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Exa API configuration
EXA_API_KEY = os.getenv("EXA_API_KEY", "1bd9f337-d3ee-4010-bc85-f10939fcafe0")
EXA_API_URL = "https://api.exa.ai/search"

def search_web(query: str, max_results: int = 5, use_exa: bool = True) -> List[Dict[str, Any]]:
    """
    Search web content and return summaries
    
    Args:
        query: Search query string
        max_results: Maximum number of results
        use_exa: Whether to use Exa API (default True)
    
    Returns:
        List of dictionaries containing web content and summaries
    """
    if use_exa:
        return _search_with_exa(query, max_results)
    else:
        # Fallback: use other search API or crawler
        return _search_fallback(query, max_results)

def _search_with_exa(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Search using Exa API"""
    try:
        headers = {
            "Authorization": f"Bearer {EXA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "numResults": max_results,
            "contents": {
                "text": True,
                "highlights": True,
                "summary": True
            },
            "useAutoprompt": True
        }
        
        response = requests.post(EXA_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for item in data.get("results", []):
            # 从不同可能的字段中提取内容
            content = ""
            if "text" in item:
                content = item["text"]
            elif "contents" in item and "text" in item["contents"]:
                content = item["contents"]["text"]
            
            # 提取摘要/高亮
            summary = ""
            if "highlights" in item:
                highlights = item["highlights"]
                if isinstance(highlights, list) and highlights:
                    summary = highlights[0]
                elif isinstance(highlights, str):
                    summary = highlights
            elif "summary" in item:
                summary = item["summary"]
            
            result = {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": content,
                "summary": summary,
                "published_date": item.get("publishedDate", item.get("published_date", "")),
                "author": item.get("author", ""),
                "score": item.get("score", 0.0),
                "search_timestamp": datetime.now().isoformat()
            }
            results.append(result)
        
        logger.info(f"Exa API search successful: {query}, returned {len(results)} results")
        return results
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Exa API request failed: {e}")
        # Fallback to alternative solution
        return _search_fallback(query, max_results)
    except Exception as e:
        logger.error(f"Exa API processing failed: {e}")
        return []

def _search_fallback(query: str, max_results: int) -> List[Dict[str, Any]]:
    """
    Fallback search solution (can use Google Custom Search API, Bing API, etc.)
    This provides a mock implementation
    """
    logger.warning(f"Using fallback search solution: {query}")
    
    # Mock data, should actually call other search APIs
    mock_results = []
    
    # Mock results for specific sites
    if "statista.com" in query:
        mock_results.append({
            "url": "https://www.statista.com/statistics/xxx",
            "title": "Market Size Statistics",
            "content": "The global market for this disease treatment was valued at $X billion in 2023...",
            "summary": "Market expected to grow at CAGR of X% from 2023-2030",
            "published_date": "2023-12-01",
            "author": "Statista Research",
            "score": 0.95,
            "search_timestamp": datetime.now().isoformat()
        })
    
    if "cninfo.com.cn" in query:
        mock_results.append({
            "url": "https://www.cninfo.com.cn/xxx",
            "title": "Medical Insurance Reimbursement Policy Analysis",
            "content": "This drug has been included in the national medical insurance catalog, with reimbursement rate...",
            "summary": "Included in medical insurance from 2024, 70% reimbursement rate",
            "published_date": "2024-01-15",
            "author": "China Securities Information",
            "score": 0.90,
            "search_timestamp": datetime.now().isoformat()
        })
    
    # Generic mock results
    if not mock_results:
        for i in range(min(max_results, 2)):
            mock_results.append({
                "url": f"https://example.com/article{i}",
                "title": f"Article about {query}",
                "content": f"This is mock content about {query}. In real implementation, this would be actual scraped content.",
                "summary": f"Summary of findings related to {query}",
                "published_date": "2024-01-01",
                "author": "Mock Author",
                "score": 0.8 - i * 0.1,
                "search_timestamp": datetime.now().isoformat()
            })
    
    return mock_results[:max_results]

def scrape_url(url: str) -> Dict[str, Any]:
    """
    Scrape content from a single URL
    
    Args:
        url: URL to scrape
    
    Returns:
        Dictionary containing webpage content
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # More complex content extraction logic can be added here
        # e.g., using BeautifulSoup to parse HTML
        
        return {
            "url": url,
            "content": response.text[:5000],  # Limit content length
            "status_code": response.status_code,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"URL scraping failed {url}: {e}")
        return {
            "url": url,
            "content": "",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Export functions
__all__ = ["search_web", "scrape_url"]