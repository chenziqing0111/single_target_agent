# agent_core/agents/patent_agent_wrapper.py
# 专利Agent工作流包装器 - 集成真实专利API，移除所有模拟数据

import logging
from typing import Dict, Any
from enum import Enum

from agent_core.agents.specialists.patent_expert import PatentExpert, analyze_patent_sync

logger = logging.getLogger(__name__)

class PatentAnalysisMode(Enum):
    """专利分析模式 - 基于真实API数据"""
    QUICK = "QUICK"       # 快速: 15个专利, 单一数据源
    STANDARD = "STANDARD" # 标准: 30个专利, 主要数据源
    DEEP = "DEEP"         # 深度: 50个专利, 所有可用数据源

def patent_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    专利Agent节点函数 - 基于真实专利API的工作流集成
    
    Args:
        state: 工作流状态字典，包含：
            - gene: 目标基因 (必需)
            - config: 分析配置 (可选)
            - context: 额外上下文 (可选)
    
    Returns:
        更新后的状态字典，添加专利分析结果
    """
    try:
        # 1. 参数提取和验证
        gene = state.get("gene", "").strip()
        if not gene:
            logger.warning("专利分析：未提供有效的基因名称")
            state["patent_result"] = "❌ 未提供基因名称，无法进行专利分析"
            state["patent_analysis_data"] = None
            return state
        
        # 2. 模式配置 - 从config或context中获取
        config = state.get("config", {})
        context = state.get("context", {})
        
        # 尝试从多个地方获取分析模式
        mode_str = (
            config.get("analysis_mode") or 
            context.get("analysis_mode") or 
            state.get("analysis_mode") or 
            "STANDARD"
        ).upper()
        
        try:
            analysis_mode = PatentAnalysisMode(mode_str)
        except ValueError:
            logger.warning(f"无效的分析模式: {mode_str}，使用默认模式")
            analysis_mode = PatentAnalysisMode.STANDARD
        
        logger.info(f"🔍 开始真实专利API分析: {gene} (模式: {analysis_mode.value})")
        
        # 3. 准备上下文参数
        analysis_context = {
            "additional_terms": context.get("additional_terms", []),
            "patent_focus_areas": context.get("patent_focus_areas", context.get("focus_areas", [])),
            "analysis_mode": analysis_mode.value
        }
        
        # 4. 执行分析 - 使用真实专利API
        expert = PatentExpert(mode=analysis_mode.value)
        result = expert.analyze_sync(gene, analysis_context)
        
        # 5. 生成报告
        report_content = expert.generate_summary_report(result)
        
        # 6. 更新状态
        state["patent_result"] = report_content
        state["patent_analysis_data"] = result.to_dict()
        state["patent_key_findings"] = {
            "target": result.target,
            "total_patents": result.total_patents,
            "key_patents": result.key_patents[:5],
            "main_recommendations": result.recommendations[:3],
            "confidence": result.confidence_score,
            "data_sources": result.data_sources,
            "analysis_mode": analysis_mode.value,
            "data_type": "真实专利API数据",
            "api_version": expert.version
        }
        
        logger.info(f"✅ 真实专利API分析完成: 发现 {result.total_patents} 项专利 (置信度: {result.confidence_score:.0%}, 数据源: {len(result.data_sources)}个)")
        
    except Exception as e:
        logger.error(f"❌ 真实专利API分析失败: {e}")
        state["patent_result"] = f"专利分析过程中发生错误: {str(e)}。这可能是由于网络连接问题或API限制导致，请稍后重试。"
        state["patent_analysis_data"] = None
        state["patent_key_findings"] = {
            "target": gene,
            "total_patents": 0,
            "error": str(e),
            "data_sources": [],
            "analysis_mode": analysis_mode.value if 'analysis_mode' in locals() else "UNKNOWN",
            "data_type": "分析失败"
        }
    
    return state

def _generate_patent_report(result) -> str:
    """生成专利分析报告文本（兼容性函数）"""
    # 创建专家实例生成报告
    expert = PatentExpert()
    return expert.generate_summary_report(result)

# 异步版本的包装器
async def patent_agent_async(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    异步版本的专利Agent节点函数 - 基于真实专利API
    """
    try:
        # 提取参数
        gene = state.get("gene", "").strip()
        config = state.get("config", {})
        context = state.get("context", {})
        
        if not gene:
            logger.warning("专利分析：未提供基因名称")
            state["patent_result"] = "未提供基因名称，无法进行专利分析"
            return state
        
        # 分析模式配置
        mode_str = (
            config.get("analysis_mode") or 
            context.get("analysis_mode") or 
            state.get("analysis_mode") or 
            "STANDARD"
        ).upper()
        
        try:
            analysis_mode = PatentAnalysisMode(mode_str)
        except ValueError:
            logger.warning(f"无效的分析模式: {mode_str}，使用默认模式")
            analysis_mode = PatentAnalysisMode.STANDARD
        
        logger.info(f"开始异步真实专利API分析：{gene} (模式: {analysis_mode.value})")
        
        # 准备上下文参数
        analysis_context = {
            "additional_terms": context.get("additional_terms", []),
            "patent_focus_areas": context.get("patent_focus_areas", context.get("focus_areas", [])),
            "analysis_mode": analysis_mode.value
        }
        
        # 创建专利专家实例并运行异步分析
        expert = PatentExpert(mode=analysis_mode.value)
        result = await expert.analyze(gene, analysis_context)
        
        # 生成报告内容
        report_content = expert.generate_summary_report(result)
        
        # 更新状态
        state["patent_result"] = report_content
        state["patent_analysis_data"] = result.to_dict()
        state["patent_key_findings"] = {
            "target": result.target,
            "total_patents": result.total_patents,
            "key_patents": result.key_patents[:5] if result.key_patents else [],
            "main_recommendations": result.recommendations[:3] if result.recommendations else [],
            "confidence": result.confidence_score,
            "data_sources": result.data_sources,
            "analysis_mode": analysis_mode.value,
            "data_type": "真实专利API数据",
            "api_version": expert.version
        }
        
        logger.info(f"异步真实专利API分析完成：发现 {result.total_patents} 项相关专利 (置信度: {result.confidence_score:.0%})")
        
    except Exception as e:
        logger.error(f"异步专利分析失败: {e}")
        state["patent_result"] = f"专利分析过程中发生错误: {str(e)}。这可能是由于网络连接问题或API限制导致，请稍后重试。"
        state["patent_analysis_data"] = None
        state["patent_key_findings"] = {
            "target": gene,
            "total_patents": 0,
            "error": str(e),
            "data_sources": [],
            "analysis_mode": analysis_mode.value if 'analysis_mode' in locals() else "UNKNOWN",
            "data_type": "分析失败"
        }
    
    return state

# 配置管理器（兼容性）
class ConfigManager:
    """简化的配置管理器"""
    
    @staticmethod
    def get_mode_config(mode: PatentAnalysisMode) -> Dict[str, Any]:
        """获取模式配置 - 基于真实专利API"""
        configs = {
            PatentAnalysisMode.QUICK: {
                "max_patents": 15,
                "sources": ['patentsview'],
                "analysis_depth": "basic",
                "timeout": 45,
                "description": "快速模式: 使用PatentsView API，基础分析，适合初步调研"
            },
            PatentAnalysisMode.STANDARD: {
                "max_patents": 30,
                "sources": ['patentsview', 'google'],
                "analysis_depth": "standard", 
                "timeout": 90,
                "description": "标准模式: 使用多个数据源，全面分析，适合常规研究"
            },
            PatentAnalysisMode.DEEP: {
                "max_patents": 50,
                "sources": ['patentsview', 'google', 'uspto'],
                "analysis_depth": "comprehensive",
                "timeout": 180,
                "description": "深度模式: 使用所有可用API，详细分析，适合专业研究"
            }
        }
        return configs.get(mode, configs[PatentAnalysisMode.STANDARD])
    
    @staticmethod
    def get_quick_config():
        """获取快速配置"""
        return ConfigManager.get_mode_config(PatentAnalysisMode.QUICK)
    
    @staticmethod 
    def get_standard_config():
        """获取标准配置"""
        return ConfigManager.get_mode_config(PatentAnalysisMode.STANDARD)
    
    @staticmethod
    def get_deep_config():
        """获取深度配置"""
        return ConfigManager.get_mode_config(PatentAnalysisMode.DEEP)

# 便捷的专利景观分析函数
def analyze_patent_landscape(gene: str, mode: str = "STANDARD", **kwargs) -> Dict[str, Any]:
    """
    独立的专利景观分析函数
    
    Args:
        gene: 目标基因
        mode: 分析模式 (QUICK/STANDARD/DEEP)
        **kwargs: 额外参数
    
    Returns:
        分析结果字典
    """
    try:
        # 构建状态
        state = {
            "gene": gene,
            "analysis_mode": mode.upper(),
            "context": kwargs
        }
        
        # 执行分析
        result_state = patent_agent(state)
        
        return {
            "success": True,
            "gene": gene,
            "mode": mode.upper(),
            "report": result_state.get("patent_result", ""),
            "data": result_state.get("patent_analysis_data", {}),
            "key_findings": result_state.get("patent_key_findings", {}),
            "error": None
        }
        
    except Exception as e:
        logger.error(f"专利分析失败: {e}")
        return {
            "success": False,
            "gene": gene,
            "mode": mode.upper(),
            "report": f"分析失败: {str(e)}",
            "data": {},
            "key_findings": {},
            "error": str(e)
        }

# 测试函数
def test_patent_agent_wrapper():
    """测试真实专利API包装器"""
    print("🧪 测试真实专利API包装器")
    print("=" * 50)
    
    # 测试1: 工作流节点函数
    print("\n1. 测试工作流节点函数 (真实API):")
    state = {
        "gene": "HDAC1",
        "analysis_mode": "QUICK",
        "context": {
            "patent_focus_areas": ["therapy", "CRISPR"],
            "additional_terms": ["histone", "deacetylase"]
        }
    }
    
    try:
        result_state = patent_agent(state)
        
        if "patent_result" in result_state and "专利分析过程中发生错误" not in result_state["patent_result"]:
            print("✅ 真实专利API分析成功")
            findings = result_state['patent_key_findings']
            print(f"发现专利数: {findings['total_patents']}")
            print(f"分析置信度: {findings['confidence']:.0%}")
            print(f"分析模式: {findings['analysis_mode']}")
            print(f"数据源: {', '.join(findings['data_sources'])}")
            print(f"数据类型: {findings['data_type']}")
        else:
            print("❌ 专利分析失败")
            if result_state.get('patent_key_findings'):
                print(f"错误信息: {result_state['patent_key_findings'].get('error', 'Unknown')}")
    except Exception as e:
        print(f"❌ 测试1失败: {e}")
    
    # 测试2: 独立分析函数
    print("\n2. 测试独立分析函数 (真实API):")
    try:
        analysis = analyze_patent_landscape(
            "BRCA1",
            mode="STANDARD",
            focus_areas=["diagnostic", "therapy"],
            additional_terms=["breast cancer", "ovarian cancer"]
        )
        
        if analysis["success"]:
            print("✅ 独立分析成功")
            print(f"专利总数: {analysis['key_findings']['total_patents']}")
            print(f"数据源: {', '.join(analysis['key_findings']['data_sources'])}")
            print(f"API版本: {analysis['key_findings'].get('api_version', 'N/A')}")
        else:
            print("❌ 独立分析失败")
            print(f"错误: {analysis['error']}")
            
    except Exception as e:
        print(f"❌ 测试2失败: {e}")
    
    # 测试3: 不同模式测试
    print("\n3. 测试不同分析模式 (真实API):")
    for mode in ["QUICK", "STANDARD", "DEEP"]:
        try:
            config = ConfigManager.get_mode_config(PatentAnalysisMode(mode))
            print(f"\n{mode}模式配置: {config['description']}")
            
            state = {"gene": "PCSK9", "analysis_mode": mode}
            result = patent_agent(state)
            
            if "patent_key_findings" in result and result["patent_key_findings"]:
                findings = result["patent_key_findings"]
                if "error" not in findings:
                    print(f"✅ {mode}模式: {findings['total_patents']}个专利, 置信度{findings['confidence']:.0%}")
                    print(f"   数据源: {', '.join(findings['data_sources'])}")
                else:
                    print(f"❌ {mode}模式失败: {findings['error']}")
            else:
                print(f"❌ {mode}模式无返回结果")
        except Exception as e:
            print(f"❌ {mode}模式错误: {e}")
    
    # 测试4: API配置检查
    print("\n4. API配置检查:")
    try:
        from agent_core.agents.tools.retrievers.real_patent_retriever import PATENT_API_CONFIG
        enabled_apis = [name for name, config in PATENT_API_CONFIG.items() if config.get('enabled', False)]
        print(f"启用的API: {', '.join(enabled_apis)}")
        
        if 'uspto' in enabled_apis:
            uspto_key = PATENT_API_CONFIG['uspto'].get('api_key')
            print(f"USPTO API Key: {'已配置' if uspto_key else '未配置'}")
            
    except Exception as e:
        print(f"❌ API配置检查失败: {e}")

if __name__ == "__main__":
    test_patent_agent_wrapper()