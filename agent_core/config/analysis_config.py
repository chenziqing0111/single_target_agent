# agent_core/config/analysis_config.py

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum

class AnalysisMode(Enum):
    """分析模式枚举"""
    QUICK = "quick"          # 快速测试模式
    STANDARD = "standard"    # 标准分析模式  
    DEEP = "deep"           # 深度分析模式
    CUSTOM = "custom"       # 自定义模式

@dataclass
class ClinicalTrialsConfig:
    """临床试验检索配置"""
    page_size: int = 10              # 每页结果数
    max_pages: int = 2               # 最大页数
    max_trials_analyze: int = 20     # 最多分析多少个试验
    use_detailed_description: bool = True  # 是否使用详细描述
    fields_to_analyze: List[str] = None    # 要分析的字段
    
    def __post_init__(self):
        if self.fields_to_analyze is None:
            self.fields_to_analyze = ["title", "brief_summary", "condition", "phase", "status"]

@dataclass 
class LiteratureConfig:
    """文献检索配置"""
    max_abstracts: int = 20          # 最多检索多少篇文献
    max_abstracts_analyze: int = 15  # 最多分析多少篇
    abstract_max_length: int = 500   # 每篇摘要最大长度(字符)
    include_full_text: bool = False  # 是否包含全文(未来功能)

@dataclass
class AnalysisDepthConfig:
    """分析深度配置"""
    analysis_sections: List[str] = None  # 要生成的分析章节
    prompt_max_length: int = 4000        # 提示词最大长度
    response_max_tokens: int = 1500      # 响应最大token数
    include_citations: bool = True       # 是否包含引用
    generate_summary: bool = True        # 是否生成总结
    
    def __post_init__(self):
        if self.analysis_sections is None:
            self.analysis_sections = ["disease_mechanism", "treatment_strategy", "target_analysis"]

@dataclass
class TokenConfig:
    """Token使用配置"""
    max_input_tokens: int = 8000         # 最大输入token数
    max_output_tokens: int = 2000        # 最大输出token数
    estimated_tokens_per_trial: int = 150    # 每个试验预估token数
    estimated_tokens_per_abstract: int = 300 # 每篇摘要预估token数
    safety_buffer: float = 0.8           # 安全缓冲区(80%使用率)

@dataclass
class PerformanceConfig:
    """性能配置"""
    request_timeout: int = 30            # 请求超时时间(秒)
    request_delay: float = 0.3           # 请求间隔(秒)
    max_concurrent_requests: int = 3     # 最大并发请求数
    enable_caching: bool = True          # 是否启用缓存
    cache_ttl: int = 3600               # 缓存生存时间(秒)

@dataclass
class AnalysisConfig:
    """完整分析配置"""
    mode: AnalysisMode = AnalysisMode.STANDARD
    clinical_trials: ClinicalTrialsConfig = None
    literature: LiteratureConfig = None  
    analysis_depth: AnalysisDepthConfig = None
    tokens: TokenConfig = None
    performance: PerformanceConfig = None
    
    def __post_init__(self):
        # 如果没有提供子配置，使用默认值
        if self.clinical_trials is None:
            self.clinical_trials = ClinicalTrialsConfig()
        if self.literature is None:
            self.literature = LiteratureConfig()
        if self.analysis_depth is None:
            self.analysis_depth = AnalysisDepthConfig()
        if self.tokens is None:
            self.tokens = TokenConfig()
        if self.performance is None:
            self.performance = PerformanceConfig()

class ConfigManager:
    """配置管理器"""
    
    @staticmethod
    def get_quick_config() -> AnalysisConfig:
        """快速测试配置 - 省Token，快速运行"""
        return AnalysisConfig(
            mode=AnalysisMode.QUICK,
            clinical_trials=ClinicalTrialsConfig(
                page_size=3,
                max_pages=1, 
                max_trials_analyze=3,
                use_detailed_description=False,  # 👈 不使用详细描述
                fields_to_analyze=["title", "brief_summary", "condition"]  # 👈 只用核心字段
            ),
            literature=LiteratureConfig(
                max_abstracts=5,
                max_abstracts_analyze=3,
                abstract_max_length=300
            ),
            analysis_depth=AnalysisDepthConfig(
                analysis_sections=["disease_mechanism"],  # 👈 只分析疾病机制
                prompt_max_length=2000,
                response_max_tokens=800,
                include_citations=False,  # 👈 不包含引用
                generate_summary=True
            ),
            tokens=TokenConfig(
                max_input_tokens=3000,
                max_output_tokens=1000,
                estimated_tokens_per_trial=100,
                estimated_tokens_per_abstract=200
            )
        )
    
    @staticmethod 
    def get_standard_config() -> AnalysisConfig:
        """标准配置 - 平衡质量和效率"""
        return AnalysisConfig(
            mode=AnalysisMode.STANDARD,
            clinical_trials=ClinicalTrialsConfig(
                page_size=10,
                max_pages=2,
                max_trials_analyze=15,
                use_detailed_description=True,
                fields_to_analyze=["title", "brief_summary", "detailed_description", "condition", "phase", "status"]
            ),
            literature=LiteratureConfig(
                max_abstracts=20,
                max_abstracts_analyze=10,
                abstract_max_length=500
            ),
            analysis_depth=AnalysisDepthConfig(
                analysis_sections=["disease_mechanism", "treatment_strategy"],
                prompt_max_length=4000,
                response_max_tokens=1500,
                include_citations=True,
                generate_summary=True
            ),
            tokens=TokenConfig(
                max_input_tokens=8000,
                max_output_tokens=2000
            )
        )
    
    @staticmethod
    def get_deep_config() -> AnalysisConfig:
        """深度分析配置 - 最全面的分析"""
        return AnalysisConfig(
            mode=AnalysisMode.DEEP,
            clinical_trials=ClinicalTrialsConfig(
                page_size=20,
                max_pages=3,
                max_trials_analyze=50,
                use_detailed_description=True,
                fields_to_analyze=["title", "brief_summary", "detailed_description", "condition", "phase", "status", "interventions", "outcomes"]
            ),
            literature=LiteratureConfig(
                max_abstracts=50,
                max_abstracts_analyze=30,
                abstract_max_length=800
            ),
            analysis_depth=AnalysisDepthConfig(
                analysis_sections=["disease_mechanism", "treatment_strategy", "target_analysis"],
                prompt_max_length=8000,
                response_max_tokens=3000,
                include_citations=True,
                generate_summary=True
            ),
            tokens=TokenConfig(
                max_input_tokens=15000,
                max_output_tokens=4000
            )
        )
    
    @staticmethod
    def get_config_by_mode(mode: AnalysisMode) -> AnalysisConfig:
        """根据模式获取配置"""
        if mode == AnalysisMode.QUICK:
            return ConfigManager.get_quick_config()
        elif mode == AnalysisMode.STANDARD:
            return ConfigManager.get_standard_config()
        elif mode == AnalysisMode.DEEP:
            return ConfigManager.get_deep_config()
        else:
            return ConfigManager.get_standard_config()
    
    @staticmethod
    def estimate_token_usage(config: AnalysisConfig) -> Dict[str, int]:
        """估算Token使用量"""
        ct_config = config.clinical_trials
        lit_config = config.literature
        token_config = config.tokens
        
        # 估算输入token
        trials_tokens = ct_config.max_trials_analyze * token_config.estimated_tokens_per_trial
        abstracts_tokens = lit_config.max_abstracts_analyze * token_config.estimated_tokens_per_abstract
        prompt_tokens = 500  # 基础提示词
        
        input_tokens = trials_tokens + abstracts_tokens + prompt_tokens
        
        # 估算输出token
        output_tokens = config.analysis_depth.response_max_tokens * len(config.analysis_depth.analysis_sections)
        
        total_tokens = input_tokens + output_tokens
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens, 
            "total_tokens": total_tokens,
            "trials_tokens": trials_tokens,
            "abstracts_tokens": abstracts_tokens,
            "estimated_cost_usd": total_tokens * 0.000002  # 粗略估算成本
        }
    
    @staticmethod
    def validate_config(config: AnalysisConfig) -> List[str]:
        """验证配置合理性"""
        warnings = []
        
        # 检查Token限制
        token_estimate = ConfigManager.estimate_token_usage(config)
        if token_estimate["total_tokens"] > config.tokens.max_input_tokens + config.tokens.max_output_tokens:
            warnings.append(f"估算Token使用量({token_estimate['total_tokens']})超过限制")
        
        # 检查数据量
        if config.clinical_trials.max_trials_analyze > 100:
            warnings.append("试验分析数量过多，可能导致超时")
            
        if config.literature.max_abstracts_analyze > 50:
            warnings.append("文献分析数量过多，可能导致超时")
        
        # 检查逻辑一致性
        if config.clinical_trials.max_trials_analyze > config.clinical_trials.page_size * config.clinical_trials.max_pages:
            warnings.append("要分析的试验数量超过检索数量")
            
        return warnings

# 使用示例和测试
def example_usage():
    """配置使用示例"""
    
    print("=== 配置示例 ===")
    
    # 1. 快速模式
    quick_config = ConfigManager.get_quick_config()
    quick_estimate = ConfigManager.estimate_token_usage(quick_config)
    print(f"快速模式预估Token: {quick_estimate['total_tokens']}")
    print(f"预估成本: ${quick_estimate['estimated_cost_usd']:.4f}")
    
    # 2. 标准模式
    standard_config = ConfigManager.get_standard_config()
    standard_estimate = ConfigManager.estimate_token_usage(standard_config)
    print(f"标准模式预估Token: {standard_estimate['total_tokens']}")
    
    # 3. 深度模式
    deep_config = ConfigManager.get_deep_config()
    deep_estimate = ConfigManager.estimate_token_usage(deep_config)
    print(f"深度模式预估Token: {deep_estimate['total_tokens']}")
    
    # 4. 验证配置
    warnings = ConfigManager.validate_config(deep_config)
    if warnings:
        print(f"深度模式警告: {warnings}")
    
    # 5. 自定义配置
    custom_config = AnalysisConfig(
        mode=AnalysisMode.CUSTOM,
        clinical_trials=ClinicalTrialsConfig(
            page_size=5,
            max_pages=1,
            use_detailed_description=False
        )
    )
    custom_estimate = ConfigManager.estimate_token_usage(custom_config)
    print(f"自定义配置预估Token: {custom_estimate['total_tokens']}")

if __name__ == "__main__":
    example_usage()