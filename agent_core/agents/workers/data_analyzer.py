# agent_core/agents/workers/data_analyzer.py

import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from collections import Counter, defaultdict
import re
import logging

logger = logging.getLogger(__name__)

@dataclass
class AnalysisResult:
    """分析结果数据结构"""
    analysis_type: str
    data_summary: Dict[str, Any]
    insights: List[str]
    confidence_score: float
    metadata: Dict[str, Any]

class DataAnalyzer:
    """数据分析器 - 提供各种数据分析功能"""
    
    def __init__(self):
        self.name = "Data Analyzer"
        self.version = "1.0.0"
        
    async def analyze(self, data: Any, analysis_type: str, **kwargs) -> AnalysisResult:
        """
        通用分析入口
        
        Args:
            data: 要分析的数据
            analysis_type: 分析类型 (statistical, temporal, text, network)
            **kwargs: 额外参数
        
        Returns:
            AnalysisResult: 分析结果
        """
        
        analyzers = {
            "statistical": self._statistical_analysis,
            "temporal": self._temporal_analysis, 
            "text": self._text_analysis,
            "network": self._network_analysis,
            "distribution": self._distribution_analysis,
            "trend": self._trend_analysis
        }
        
        analyzer = analyzers.get(analysis_type)
        if not analyzer:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
        
        try:
            return await analyzer(data, **kwargs)
        except Exception as e:
            logger.error(f"Analysis error ({analysis_type}): {str(e)}")
            return AnalysisResult(
                analysis_type=analysis_type,
                data_summary={"error": str(e)},
                insights=[],
                confidence_score=0.0,
                metadata={"error": True}
            )
    
    async def _statistical_analysis(self, data: List[Dict], **kwargs) -> AnalysisResult:
        """统计分析"""
        
        if not data:
            return self._empty_result("statistical", "No data provided")
        
        summary = {
            "total_count": len(data),
            "data_types": self._analyze_data_types(data),
            "missing_values": self._analyze_missing_values(data),
            "key_statistics": self._calculate_key_statistics(data)
        }
        
        insights = self._generate_statistical_insights(summary)
        confidence = self._calculate_statistical_confidence(data, summary)
        
        return AnalysisResult(
            analysis_type="statistical",
            data_summary=summary,
            insights=insights,
            confidence_score=confidence,
            metadata={"sample_size": len(data)}
        )
    
    async def _temporal_analysis(self, data: List[Dict], date_field: str = "date", **kwargs) -> AnalysisResult:
        """时间序列分析"""
        
        if not data:
            return self._empty_result("temporal", "No data provided")
        
        # 提取时间数据
        temporal_data = self._extract_temporal_data(data, date_field)
        
        summary = {
            "time_range": self._calculate_time_range(temporal_data),
            "frequency_distribution": self._calculate_frequency_distribution(temporal_data),
            "trend_analysis": self._analyze_temporal_trends(temporal_data),
            "seasonality": self._detect_seasonality(temporal_data),
            "peak_periods": self._identify_peak_periods(temporal_data)
        }
        
        insights = self._generate_temporal_insights(summary)
        confidence = self._calculate_temporal_confidence(temporal_data, summary)
        
        return AnalysisResult(
            analysis_type="temporal",
            data_summary=summary,
            insights=insights,
            confidence_score=confidence,
            metadata={"temporal_points": len(temporal_data)}
        )
    
    async def _text_analysis(self, data: List[Dict], text_fields: List[str] = None, **kwargs) -> AnalysisResult:
        """文本分析"""
        
        if not data:
            return self._empty_result("text", "No data provided")
        
        # 默认文本字段
        if text_fields is None:
            text_fields = ["title", "description", "summary", "content"]
        
        # 提取文本内容
        texts = self._extract_text_content(data, text_fields)
        
        summary = {
            "total_texts": len(texts),
            "word_frequency": self._analyze_word_frequency(texts),
            "key_phrases": self._extract_key_phrases(texts),
            "sentiment_analysis": self._analyze_sentiment(texts),
            "text_statistics": self._calculate_text_statistics(texts)
        }
        
        insights = self._generate_text_insights(summary)
        confidence = self._calculate_text_confidence(texts, summary)
        
        return AnalysisResult(
            analysis_type="text",
            data_summary=summary,
            insights=insights,
            confidence_score=confidence,
            metadata={"text_count": len(texts)}
        )
    
    async def _network_analysis(self, data: List[Dict], **kwargs) -> AnalysisResult:
        """网络分析"""
        
        # 构建关系网络
        network = self._build_network(data)
        
        summary = {
            "node_count": len(network.get("nodes", [])),
            "edge_count": len(network.get("edges", [])),
            "centrality_analysis": self._analyze_centrality(network),
            "clustering": self._analyze_clustering(network),
            "communities": self._detect_communities(network)
        }
        
        insights = self._generate_network_insights(summary)
        confidence = self._calculate_network_confidence(network, summary)
        
        return AnalysisResult(
            analysis_type="network",
            data_summary=summary,
            insights=insights,
            confidence_score=confidence,
            metadata={"network_density": self._calculate_network_density(network)}
        )
    
    async def _distribution_analysis(self, data: List[Dict], field: str, **kwargs) -> AnalysisResult:
        """分布分析"""
        
        # 提取指定字段的值
        values = self._extract_field_values(data, field)
        
        summary = {
            "value_distribution": Counter(values),
            "unique_values": len(set(values)),
            "top_values": self._get_top_values(values, 10),
            "distribution_type": self._determine_distribution_type(values),
            "outliers": self._detect_outliers(values)
        }
        
        insights = self._generate_distribution_insights(summary, field)
        confidence = self._calculate_distribution_confidence(values, summary)
        
        return AnalysisResult(
            analysis_type="distribution",
            data_summary=summary,
            insights=insights,
            confidence_score=confidence,
            metadata={"field": field, "sample_size": len(values)}
        )
    
    async def _trend_analysis(self, data: List[Dict], **kwargs) -> AnalysisResult:
        """趋势分析"""
        
        time_field = kwargs.get("time_field", "date")
        value_field = kwargs.get("value_field", "value")
        
        # 构建时间序列
        time_series = self._build_time_series(data, time_field, value_field)
        
        summary = {
            "trend_direction": self._calculate_trend_direction(time_series),
            "trend_strength": self._calculate_trend_strength(time_series),
            "change_points": self._detect_change_points(time_series),
            "forecasting": self._simple_forecast(time_series),
            "correlation_analysis": self._analyze_correlations(time_series)
        }
        
        insights = self._generate_trend_insights(summary)
        confidence = self._calculate_trend_confidence(time_series, summary)
        
        return AnalysisResult(
            analysis_type="trend",
            data_summary=summary,
            insights=insights,
            confidence_score=confidence,
            metadata={"time_series_length": len(time_series)}
        )
    
    # 辅助方法
    def _analyze_data_types(self, data: List[Dict]) -> Dict[str, str]:
        """分析数据类型"""
        type_analysis = {}
        
        if data:
            sample = data[0]
            for key, value in sample.items():
                type_analysis[key] = type(value).__name__
        
        return type_analysis
    
    def _analyze_missing_values(self, data: List[Dict]) -> Dict[str, int]:
        """分析缺失值"""
        missing_count = defaultdict(int)
        
        for record in data:
            for key in record.keys():
                if not record.get(key) or record[key] in [None, "", "Unknown"]:
                    missing_count[key] += 1
        
        return dict(missing_count)
    
    def _calculate_key_statistics(self, data: List[Dict]) -> Dict[str, Any]:
        """计算关键统计信息"""
        return {
            "total_records": len(data),
            "fields_count": len(data[0].keys()) if data else 0,
            "completeness_ratio": self._calculate_completeness_ratio(data)
        }
    
    def _calculate_completeness_ratio(self, data: List[Dict]) -> float:
        """计算数据完整性比例"""
        if not data:
            return 0.0
        
        total_fields = len(data) * len(data[0].keys()) if data else 0
        missing_values = sum(self._analyze_missing_values(data).values())
        
        return (total_fields - missing_values) / total_fields if total_fields > 0 else 0.0
    
    def _extract_temporal_data(self, data: List[Dict], date_field: str) -> List[str]:
        """提取时间数据"""
        temporal_data = []
        
        for record in data:
            date_value = record.get(date_field)
            if date_value and date_value != "Unknown":
                temporal_data.append(str(date_value))
        
        return temporal_data
    
    def _calculate_time_range(self, temporal_data: List[str]) -> Dict[str, str]:
        """计算时间范围"""
        if not temporal_data:
            return {"start": "Unknown", "end": "Unknown"}
        
        sorted_dates = sorted(temporal_data)
        return {
            "start": sorted_dates[0],
            "end": sorted_dates[-1],
            "span": f"{len(set(temporal_data))} unique dates"
        }
    
    def _calculate_frequency_distribution(self, temporal_data: List[str]) -> Dict[str, int]:
        """计算频率分布"""
        return dict(Counter(temporal_data))
    
    def _analyze_temporal_trends(self, temporal_data: List[str]) -> str:
        """分析时间趋势"""
        if len(temporal_data) < 2:
            return "Insufficient data"
        
        # 简单的年度趋势分析
        yearly_counts = defaultdict(int)
        for date in temporal_data:
            year = date[:4] if len(date) >= 4 and date[:4].isdigit() else "Unknown"
            yearly_counts[year] += 1
        
        if len(yearly_counts) >= 2:
            years = sorted(yearly_counts.keys())
            if years[-1] != "Unknown" and len(years) >= 2:
                recent_count = yearly_counts[years[-1]]
                older_count = yearly_counts[years[0]]
                
                if recent_count > older_count:
                    return "Increasing trend"
                elif recent_count < older_count:
                    return "Decreasing trend"
                else:
                    return "Stable trend"
        
        return "Trend unclear"
    
    def _detect_seasonality(self, temporal_data: List[str]) -> str:
        """检测季节性"""
        # 简化的季节性检测
        return "Seasonality analysis not implemented"
    
    def _identify_peak_periods(self, temporal_data: List[str]) -> List[str]:
        """识别高峰期"""
        freq_dist = Counter(temporal_data)
        if not freq_dist:
            return []
        
        max_count = max(freq_dist.values())
        peaks = [date for date, count in freq_dist.items() if count == max_count]
        
        return peaks[:5]  # 返回前5个
    
    def _extract_text_content(self, data: List[Dict], text_fields: List[str]) -> List[str]:
        """提取文本内容"""
        texts = []
        
        for record in data:
            text_parts = []
            for field in text_fields:
                if field in record and record[field]:
                    text_parts.append(str(record[field]))
            
            if text_parts:
                texts.append(" ".join(text_parts))
        
        return texts
    
    def _analyze_word_frequency(self, texts: List[str]) -> Dict[str, int]:
        """分析词频"""
        if not texts:
            return {}
        
        # 简单的词频分析
        all_words = []
        for text in texts:
            # 简单的词分割（实际应用中应使用更复杂的NLP处理）
            words = re.findall(r'\b\w+\b', text.lower())
            # 过滤常见停用词
            stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            words = [word for word in words if word not in stop_words and len(word) > 2]
            all_words.extend(words)
        
        word_freq = Counter(all_words)
        return dict(word_freq.most_common(20))  # 返回前20个最常见的词
    
    def _extract_key_phrases(self, texts: List[str]) -> List[str]:
        """提取关键短语"""
        # 简化的关键短语提取
        phrases = []
        
        for text in texts:
            # 查找常见的医学短语模式
            medical_patterns = [
                r'\b\w+\s+trial\b',
                r'\b\w+\s+therapy\b',
                r'\b\w+\s+treatment\b',
                r'\b\w+\s+inhibitor\b',
                r'\bphase\s+\w+\b'
            ]
            
            for pattern in medical_patterns:
                matches = re.findall(pattern, text.lower())
                phrases.extend(matches)
        
        return list(set(phrases))[:10]  # 返回前10个唯一短语
    
    def _analyze_sentiment(self, texts: List[str]) -> Dict[str, Any]:
        """情感分析（简化版）"""
        # 简化的情感分析
        positive_words = {"effective", "successful", "improved", "beneficial", "positive", "promising"}
        negative_words = {"failed", "unsuccessful", "adverse", "negative", "declined", "terminated"}
        
        sentiment_scores = []
        for text in texts:
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count + negative_count > 0:
                sentiment_score = (positive_count - negative_count) / (positive_count + negative_count)
            else:
                sentiment_score = 0
            
            sentiment_scores.append(sentiment_score)
        
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        
        return {
            "average_sentiment": avg_sentiment,
            "sentiment_distribution": {
                "positive": len([s for s in sentiment_scores if s > 0]),
                "neutral": len([s for s in sentiment_scores if s == 0]),
                "negative": len([s for s in sentiment_scores if s < 0])
            }
        }
    
    def _calculate_text_statistics(self, texts: List[str]) -> Dict[str, float]:
        """计算文本统计信息"""
        if not texts:
            return {}
        
        word_counts = [len(text.split()) for text in texts]
        char_counts = [len(text) for text in texts]
        
        return {
            "avg_word_count": sum(word_counts) / len(word_counts),
            "avg_char_count": sum(char_counts) / len(char_counts),
            "total_words": sum(word_counts),
            "total_chars": sum(char_counts)
        }
    
    # 生成洞察的方法
    def _generate_statistical_insights(self, summary: Dict) -> List[str]:
        """生成统计洞察"""
        insights = []
        
        total_count = summary.get("total_count", 0)
        if total_count > 100:
            insights.append(f"Large dataset with {total_count} records provides good statistical power")
        elif total_count > 20:
            insights.append(f"Moderate dataset size ({total_count} records) allows for meaningful analysis")
        else:
            insights.append(f"Small dataset ({total_count} records) may limit statistical conclusions")
        
        completeness = summary.get("key_statistics", {}).get("completeness_ratio", 0)
        if completeness > 0.9:
            insights.append("High data completeness ensures reliable analysis")
        elif completeness > 0.7:
            insights.append("Moderate data completeness with some missing values")
        else:
            insights.append("Low data completeness may affect analysis reliability")
        
        return insights
    
    def _generate_temporal_insights(self, summary: Dict) -> List[str]:
        """生成时间洞察"""
        insights = []
        
        trend = summary.get("trend_analysis", "")
        if "increasing" in trend.lower():
            insights.append("Activity is showing an increasing trend over time")
        elif "decreasing" in trend.lower():
            insights.append("Activity is showing a decreasing trend over time")
        elif "stable" in trend.lower():
            insights.append("Activity remains relatively stable over time")
        
        time_range = summary.get("time_range", {})
        if time_range.get("start") and time_range.get("end"):
            insights.append(f"Data spans from {time_range['start']} to {time_range['end']}")
        
        return insights
    
    def _generate_text_insights(self, summary: Dict) -> List[str]:
        """生成文本洞察"""
        insights = []
        
        word_freq = summary.get("word_frequency", {})
        if word_freq:
            top_word = max(word_freq.items(), key=lambda x: x[1])
            insights.append(f"Most frequent term: '{top_word[0]}' appears {top_word[1]} times")
        
        sentiment = summary.get("sentiment_analysis", {})
        avg_sentiment = sentiment.get("average_sentiment", 0)
        if avg_sentiment > 0.1:
            insights.append("Overall sentiment tends to be positive")
        elif avg_sentiment < -0.1:
            insights.append("Overall sentiment tends to be negative")
        else:
            insights.append("Overall sentiment is neutral")
        
        return insights
    
    def _generate_network_insights(self, summary: Dict) -> List[str]:
        """生成网络洞察"""
        insights = []
        node_count = summary.get("node_count", 0)
        edge_count = summary.get("edge_count", 0)
        
        if node_count > 0:
            density = edge_count / (node_count * (node_count - 1) / 2) if node_count > 1 else 0
            if density > 0.5:
                insights.append("High network connectivity")
            elif density > 0.2:
                insights.append("Moderate network connectivity")
            else:
                insights.append("Sparse network connectivity")
        
        return insights
    
    def _generate_distribution_insights(self, summary: Dict, field: str) -> List[str]:
        """生成分布洞察"""
        insights = []
        
        unique_values = summary.get("unique_values", 0)
        total_values = sum(summary.get("value_distribution", {}).values())
        
        if unique_values == total_values:
            insights.append(f"All {field} values are unique")
        elif unique_values / total_values > 0.8:
            insights.append(f"High diversity in {field} values")
        elif unique_values / total_values > 0.5:
            insights.append(f"Moderate diversity in {field} values")
        else:
            insights.append(f"Low diversity in {field} values")
        
        top_values = summary.get("top_values", [])
        if top_values:
            top_value, top_count = top_values[0]
            percentage = (top_count / total_values) * 100
            insights.append(f"Most common {field}: '{top_value}' ({percentage:.1f}%)")
        
        return insights
    
    def _generate_trend_insights(self, summary: Dict) -> List[str]:
        """生成趋势洞察"""
        insights = []
        
        direction = summary.get("trend_direction", "")
        strength = summary.get("trend_strength", 0)
        
        if direction and strength > 0.7:
            insights.append(f"Strong {direction} trend detected")
        elif direction and strength > 0.4:
            insights.append(f"Moderate {direction} trend detected")
        elif direction:
            insights.append(f"Weak {direction} trend detected")
        else:
            insights.append("No clear trend pattern identified")
        
        return insights
    
    # 置信度计算方法
    def _calculate_statistical_confidence(self, data: List[Dict], summary: Dict) -> float:
        """计算统计分析置信度"""
        confidence = 0.5  # 基础置信度
        
        # 样本量影响
        sample_size = len(data)
        if sample_size >= 100:
            confidence += 0.3
        elif sample_size >= 30:
            confidence += 0.2
        elif sample_size >= 10:
            confidence += 0.1
        
        # 数据完整性影响
        completeness = summary.get("key_statistics", {}).get("completeness_ratio", 0)
        confidence += completeness * 0.2
        
        return min(confidence, 1.0)
    
    def _calculate_temporal_confidence(self, temporal_data: List[str], summary: Dict) -> float:
        """计算时间分析置信度"""
        confidence = 0.4
        
        if len(temporal_data) >= 20:
            confidence += 0.3
        elif len(temporal_data) >= 10:
            confidence += 0.2
        elif len(temporal_data) >= 5:
            confidence += 0.1
        
        unique_dates = len(set(temporal_data))
        if unique_dates >= 10:
            confidence += 0.2
        elif unique_dates >= 5:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_text_confidence(self, texts: List[str], summary: Dict) -> float:
        """计算文本分析置信度"""
        confidence = 0.3
        
        if len(texts) >= 50:
            confidence += 0.3
        elif len(texts) >= 20:
            confidence += 0.2
        elif len(texts) >= 10:
            confidence += 0.1
        
        avg_length = summary.get("text_statistics", {}).get("avg_word_count", 0)
        if avg_length >= 50:
            confidence += 0.2
        elif avg_length >= 20:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_network_confidence(self, network: Dict, summary: Dict) -> float:
        """计算网络分析置信度"""
        confidence = 0.4
        
        node_count = summary.get("node_count", 0)
        if node_count >= 20:
            confidence += 0.3
        elif node_count >= 10:
            confidence += 0.2
        elif node_count >= 5:
            confidence += 0.1
        
        edge_count = summary.get("edge_count", 0)
        if edge_count >= node_count:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _calculate_distribution_confidence(self, values: List, summary: Dict) -> float:
        """计算分布分析置信度"""
        confidence = 0.4
        
        if len(values) >= 100:
            confidence += 0.3
        elif len(values) >= 30:
            confidence += 0.2
        elif len(values) >= 10:
            confidence += 0.1
        
        unique_ratio = summary.get("unique_values", 0) / len(values) if values else 0
        if 0.1 <= unique_ratio <= 0.9:  # 合理的多样性
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _calculate_trend_confidence(self, time_series: List, summary: Dict) -> float:
        """计算趋势分析置信度"""
        confidence = 0.3
        
        if len(time_series) >= 20:
            confidence += 0.3
        elif len(time_series) >= 10:
            confidence += 0.2
        elif len(time_series) >= 5:
            confidence += 0.1
        
        trend_strength = summary.get("trend_strength", 0)
        confidence += trend_strength * 0.4
        
        return min(confidence, 1.0)
    
    # 其他辅助方法
    def _empty_result(self, analysis_type: str, message: str) -> AnalysisResult:
        """创建空结果"""
        return AnalysisResult(
            analysis_type=analysis_type,
            data_summary={"message": message},
            insights=[],
            confidence_score=0.0,
            metadata={"empty": True}
        )
    
    def _extract_field_values(self, data: List[Dict], field: str) -> List:
        """提取指定字段的值"""
        values = []
        for record in data:
            value = record.get(field)
            if value is not None and value != "Unknown":
                values.append(value)
        return values
    
    def _get_top_values(self, values: List, top_n: int = 10) -> List[tuple]:
        """获取最常见的值"""
        counter = Counter(values)
        return counter.most_common(top_n)
    
    def _determine_distribution_type(self, values: List) -> str:
        """确定分布类型"""
        if not values:
            return "empty"
        
        unique_count = len(set(values))
        total_count = len(values)
        
        if unique_count == total_count:
            return "uniform"
        elif unique_count / total_count > 0.8:
            return "diverse"
        elif unique_count / total_count > 0.3:
            return "moderate"
        else:
            return "concentrated"
    
    def _detect_outliers(self, values: List) -> List:
        """检测异常值（简化版）"""
        if not values or len(values) < 4:
            return []
        
        # 对于数值数据的简单异常值检测
        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                continue
        
        if len(numeric_values) < 4:
            return []
        
        # 使用IQR方法检测异常值
        sorted_values = sorted(numeric_values)
        q1_idx = len(sorted_values) // 4
        q3_idx = 3 * len(sorted_values) // 4
        
        q1 = sorted_values[q1_idx]
        q3 = sorted_values[q3_idx]
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = [v for v in numeric_values if v < lower_bound or v > upper_bound]
        return outliers[:10]  # 返回前10个异常值
    
    def _build_time_series(self, data: List[Dict], time_field: str, value_field: str) -> List[tuple]:
        """构建时间序列"""
        time_series = []
        
        for record in data:
            time_val = record.get(time_field)
            value_val = record.get(value_field)
            
            if time_val and value_val:
                try:
                    # 尝试转换为数值
                    numeric_value = float(value_val)
                    time_series.append((time_val, numeric_value))
                except (ValueError, TypeError):
                    continue
        
        # 按时间排序
        time_series.sort(key=lambda x: x[0])
        return time_series
    
    def _calculate_trend_direction(self, time_series: List[tuple]) -> str:
        """计算趋势方向"""
        if len(time_series) < 2:
            return "insufficient_data"
        
        values = [val for time, val in time_series]
        
        # 简单的线性趋势计算
        n = len(values)
        x_vals = list(range(n))
        
        # 计算斜率
        sum_x = sum(x_vals)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(x_vals, values))
        sum_x2 = sum(x * x for x in x_vals)
        
        if n * sum_x2 - sum_x * sum_x == 0:
            return "no_trend"
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_trend_strength(self, time_series: List[tuple]) -> float:
        """计算趋势强度"""
        if len(time_series) < 3:
            return 0.0
        
        values = [val for time, val in time_series]
        
        # 计算相关系数作为趋势强度
        n = len(values)
        x_vals = list(range(n))
        
        mean_x = sum(x_vals) / n
        mean_y = sum(values) / n
        
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, values))
        
        sum_sq_x = sum((x - mean_x) ** 2 for x in x_vals)
        sum_sq_y = sum((y - mean_y) ** 2 for y in values)
        
        if sum_sq_x == 0 or sum_sq_y == 0:
            return 0.0
        
        denominator = (sum_sq_x * sum_sq_y) ** 0.5
        correlation = abs(numerator / denominator)
        
        return correlation
    
    def _detect_change_points(self, time_series: List[tuple]) -> List[str]:
        """检测变化点"""
        if len(time_series) < 5:
            return []
        
        # 简化的变化点检测
        change_points = []
        values = [val for time, val in time_series]
        
        # 查找显著变化的点
        for i in range(2, len(values) - 2):
            before_avg = sum(values[i-2:i]) / 2
            after_avg = sum(values[i+1:i+3]) / 2
            
            if abs(after_avg - before_avg) > abs(before_avg) * 0.5:  # 50%变化
                change_points.append(time_series[i][0])
        
        return change_points[:5]  # 返回前5个变化点
    
    def _simple_forecast(self, time_series: List[tuple]) -> Dict[str, Any]:
        """简单预测"""
        if len(time_series) < 3:
            return {"forecast": "insufficient_data"}
        
        # 使用简单的线性外推
        direction = self._calculate_trend_direction(time_series)
        strength = self._calculate_trend_strength(time_series)
        
        last_value = time_series[-1][1]
        
        if direction == "increasing" and strength > 0.5:
            forecast_value = last_value * 1.1  # 预测增长10%
            confidence = "moderate"
        elif direction == "decreasing" and strength > 0.5:
            forecast_value = last_value * 0.9  # 预测下降10%
            confidence = "moderate"
        else:
            forecast_value = last_value  # 预测保持不变
            confidence = "low"
        
        return {
            "forecast_value": forecast_value,
            "confidence": confidence,
            "method": "linear_extrapolation"
        }
    
    def _analyze_correlations(self, time_series: List[tuple]) -> Dict[str, float]:
        """分析相关性"""
        # 简化的自相关分析
        if len(time_series) < 5:
            return {}
        
        values = [val for time, val in time_series]
        
        # 计算滞后1期的自相关
        lag1_corr = self._calculate_lag_correlation(values, 1)
        
        return {
            "lag_1_autocorrelation": lag1_corr,
            "trend_correlation": self._calculate_trend_strength(time_series)
        }
    
    def _calculate_lag_correlation(self, values: List[float], lag: int) -> float:
        """计算滞后相关性"""
        if len(values) <= lag:
            return 0.0
        
        x = values[:-lag]
        y = values[lag:]
        
        if len(x) != len(y) or len(x) == 0:
            return 0.0
        
        mean_x = sum(x) / len(x)
        mean_y = sum(y) / len(y)
        
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        
        sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
        sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)
        
        if sum_sq_x == 0 or sum_sq_y == 0:
            return 0.0
        
        denominator = (sum_sq_x * sum_sq_y) ** 0.5
        return numerator / denominator
    
    def _build_network(self, data: List[Dict]) -> Dict[str, List]:
        """构建网络（简化版）"""
        nodes = set()
        edges = []
        
        # 简化的网络构建逻辑
        for record in data:
            # 假设每个记录都有一些可以构成关系的字段
            node_id = record.get("id") or record.get("nct_id") or str(hash(str(record)))
            nodes.add(node_id)
            
            # 基于共同属性创建边
            for other_record in data:
                if record != other_record:
                    other_id = other_record.get("id") or other_record.get("nct_id") or str(hash(str(other_record)))
                    
                    # 如果有共同的sponsor或condition，创建边
                    if (record.get("sponsor") == other_record.get("sponsor") and record.get("sponsor")) or \
                       (record.get("condition") == other_record.get("condition") and record.get("condition")):
                        edges.append((node_id, other_id))
        
        return {
            "nodes": list(nodes),
            "edges": list(set(edges))  # 去重
        }
    
    def _analyze_centrality(self, network: Dict) -> Dict[str, Any]:
        """分析中心性"""
        nodes = network.get("nodes", [])
        edges = network.get("edges", [])
        
        if not nodes:
            return {}
        
        # 计算度中心性
        degree_centrality = {}
        for node in nodes:
            degree = sum(1 for edge in edges if node in edge)
            degree_centrality[node] = degree
        
        # 找出最中心的节点
        if degree_centrality:
            max_degree_node = max(degree_centrality.items(), key=lambda x: x[1])
            return {
                "degree_centrality": degree_centrality,
                "most_central_node": max_degree_node[0],
                "max_degree": max_degree_node[1]
            }
        
        return {}
    
    def _analyze_clustering(self, network: Dict) -> float:
        """分析聚类系数"""
        # 简化的全局聚类系数计算
        nodes = network.get("nodes", [])
        edges = network.get("edges", [])
        
        if len(nodes) < 3:
            return 0.0
        
        # 构建邻接表
        adj_list = defaultdict(set)
        for edge in edges:
            if len(edge) >= 2:
                adj_list[edge[0]].add(edge[1])
                adj_list[edge[1]].add(edge[0])
        
        # 计算三角形数量和可能的三角形数量
        triangles = 0
        possible_triangles = 0
        
        for node in nodes:
            neighbors = list(adj_list[node])
            if len(neighbors) >= 2:
                possible_triangles += len(neighbors) * (len(neighbors) - 1) // 2
                
                # 计算实际的三角形
                for i, neighbor1 in enumerate(neighbors):
                    for j in range(i + 1, len(neighbors)):
                        neighbor2 = neighbors[j]
                        if neighbor2 in adj_list[neighbor1]:
                            triangles += 1
        
        return (triangles / possible_triangles) if possible_triangles > 0 else 0.0
    
    def _detect_communities(self, network: Dict) -> List[List[str]]:
        """检测社区（简化版）"""
        nodes = network.get("nodes", [])
        edges = network.get("edges", [])
        
        if not nodes:
            return []
        
        # 简化的社区检测：基于连通分量
        communities = []
        unvisited = set(nodes)
        
        # 构建邻接表
        adj_list = defaultdict(set)
        for edge in edges:
            if len(edge) >= 2:
                adj_list[edge[0]].add(edge[1])
                adj_list[edge[1]].add(edge[0])
        
        # DFS寻找连通分量
        while unvisited:
            start_node = next(iter(unvisited))
            community = []
            stack = [start_node]
            
            while stack:
                node = stack.pop()
                if node in unvisited:
                    unvisited.remove(node)
                    community.append(node)
                    stack.extend(adj_list[node])
            
            if community:
                communities.append(community)
        
        return communities
    
    def _calculate_network_density(self, network: Dict) -> float:
        """计算网络密度"""
        nodes = network.get("nodes", [])
        edges = network.get("edges", [])
        
        if len(nodes) <= 1:
            return 0.0
        
        max_possible_edges = len(nodes) * (len(nodes) - 1) // 2
        actual_edges = len(edges)
        
        return actual_edges / max_possible_edges if max_possible_edges > 0 else 0.0