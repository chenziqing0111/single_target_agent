"""
Graph Definition - LangGraph图定义
完整版，包含所有节点和边的定义
"""
from typing import TypedDict, Optional, List, Any, Dict
from langgraph.graph import StateGraph, END
import asyncio
from datetime import datetime

# 导入各个专家
from agent_core.agents.specialists.literature_expert import LiteratureExpert
from agent_core.agents.specialists.clinical_expert import ClinicalExpert
from agent_core.agents.specialists.commercial_expert import CommercialExpert
from agent_core.agents.specialists.patent_expert import PatentExpert
from agent_core.agents.specialists.editor_expert import EditorExpert

class AnalysisState(TypedDict):
    """分析状态定义"""
    # 输入
    gene_name: str
    mode: str
    parallel: bool
    
    # 各agent结果
    literature_result: Optional[Any]
    clinical_result: Optional[Any]
    patent_result: Optional[Any]
    commercial_result: Optional[Any]
    
    # 最终输出
    final_report: Optional[str]
    errors: List[str]
    status: str  # initialized/running/completed/failed
    
    # 执行信息
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    execution_time: Optional[float]

# 全局专家实例（单例模式）
literature_expert = None
clinical_expert = None
patent_expert = None
commercial_expert = None
editor_expert = None

def initialize_experts(config: Dict):
    """初始化所有专家"""
    global literature_expert, clinical_expert, patent_expert, commercial_expert, editor_expert
    
    # 确保config包含必要的配置
    if 'openai_api_key' not in config:
        config['openai_api_key'] = 'sk-9b3ad78d6d51431c90091b575072e62f'
    if 'openai_base_url' not in config:
        config['openai_base_url'] = 'https://api.deepseek.com'
    
    print("[Graph] 初始化专家...")
    
    # 导入ConfigManager并创建配置对象
    from agent_core.config.analysis_config import ConfigManager
    
    # 获取deep模式的配置
    agent_config = ConfigManager.get_deep_config()
    
    # 合并自定义配置
    for key, value in config.items():
        setattr(agent_config, key, value)
    
    # 初始化专家（传递ConfigManager对象而非字典）
    if not literature_expert:
        print("  - 初始化文献专家")
        literature_expert = LiteratureExpert(agent_config)
    
    if not clinical_expert:
        print("  - 初始化临床专家")
        clinical_expert = ClinicalExpert(agent_config)
    
    if not patent_expert:
        print("  - 初始化专利专家")
        patent_expert = PatentExpert(agent_config)
    
    if not commercial_expert:
        print("  - 初始化商业专家")
        commercial_expert = CommercialExpert(agent_config)
    
    if not editor_expert:
        print("  - 初始化编辑专家")
        # Editor可能期望字典配置
        editor_expert = EditorExpert(config)
    
    print("[Graph] 所有专家初始化完成")
# ============ 节点函数 ============

async def init_node(state: AnalysisState) -> AnalysisState:
    """初始化节点"""
    print(f"[Graph] 初始化分析: {state['gene_name']}")
    state["status"] = "running"
    state["errors"] = []
    state["start_time"] = datetime.now()
    return state

async def literature_node(state: AnalysisState) -> AnalysisState:
    """文献分析节点"""
    try:
        print(f"[Graph] 开始文献分析: {state['gene_name']}")
        start = datetime.now()
        
        result = await literature_expert.analyze(state["gene_name"])
        
        duration = (datetime.now() - start).total_seconds()
        print(f"[Graph] 文献分析完成，耗时: {duration:.2f}秒")
        
        state["literature_result"] = result
        
    except Exception as e:
        error_msg = f"Literature analysis failed: {str(e)}"
        print(f"[Graph] 文献分析失败: {e}")
        state["errors"].append(error_msg)
        state["literature_result"] = None
    
    return state

async def clinical_node(state: AnalysisState) -> AnalysisState:
    """临床分析节点"""
    try:
        print(f"[Graph] 开始临床分析: {state['gene_name']}")
        start = datetime.now()
        
        result = await clinical_expert.analyze(state["gene_name"])
        
        duration = (datetime.now() - start).total_seconds()
        print(f"[Graph] 临床分析完成，耗时: {duration:.2f}秒")
        
        state["clinical_result"] = result
        
    except Exception as e:
        error_msg = f"Clinical analysis failed: {str(e)}"
        print(f"[Graph] 临床分析失败: {e}")
        state["errors"].append(error_msg)
        state["clinical_result"] = None
    
    return state

async def patent_node(state: AnalysisState) -> AnalysisState:
    """专利分析节点"""
    try:
        print(f"[Graph] 开始专利分析: {state['gene_name']}")
        start = datetime.now()
        
        result = await patent_expert.analyze(state["gene_name"])
        
        duration = (datetime.now() - start).total_seconds()
        print(f"[Graph] 专利分析完成，耗时: {duration:.2f}秒")
        
        state["patent_result"] = result
        
    except Exception as e:
        error_msg = f"Patent analysis failed: {str(e)}"
        print(f"[Graph] 专利分析失败: {e}")
        state["errors"].append(error_msg)
        state["patent_result"] = None
    
    return state

async def commercial_node(state: AnalysisState) -> AnalysisState:
    """商业分析节点"""
    try:
        print(f"[Graph] 开始商业分析: {state['gene_name']}")
        start = datetime.now()
        
        # 商业分析需要疾病领域参数
        disease = "metabolic disease"  # 默认疾病领域，后续可以从state传入
        result = await commercial_expert.analyze(state["gene_name"], disease)
        
        duration = (datetime.now() - start).total_seconds()
        print(f"[Graph] 商业分析完成，耗时: {duration:.2f}秒")
        
        state["commercial_result"] = result
        
    except Exception as e:
        error_msg = f"Commercial analysis failed: {str(e)}"
        print(f"[Graph] 商业分析失败: {e}")
        state["errors"].append(error_msg)
        state["commercial_result"] = None
    
    return state

async def parallel_analysis_node(state: AnalysisState) -> AnalysisState:
    """并行执行所有分析"""
    print(f"[Graph] 开始并行分析: {state['gene_name']}")
    start = datetime.now()
    
    # 创建所有分析任务
    tasks = []
    
    # 创建任务时传递state的副本
    async def run_with_state(node_func, state_copy):
        """运行节点并返回更新后的状态"""
        return await node_func(state_copy)
    
    # 创建各个分析任务
    tasks.append(run_with_state(literature_node, state.copy()))
    tasks.append(run_with_state(clinical_node, state.copy()))
    tasks.append(run_with_state(patent_node, state.copy()))
    tasks.append(run_with_state(commercial_node, state.copy()))
    
    # 并行执行所有任务
    print("[Graph] 并行执行4个分析任务...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 合并所有结果到主state
    for result in results:
        if isinstance(result, dict):
            # 合并各个分析结果
            if result.get("literature_result") is not None:
                state["literature_result"] = result["literature_result"]
            if result.get("clinical_result") is not None:
                state["clinical_result"] = result["clinical_result"]
            if result.get("patent_result") is not None:
                state["patent_result"] = result["patent_result"]
            if result.get("commercial_result") is not None:
                state["commercial_result"] = result["commercial_result"]
            
            # 合并错误信息
            if result.get("errors"):
                state["errors"].extend(result["errors"])
                
        elif isinstance(result, Exception):
            # 处理异常
            error_msg = f"Parallel execution error: {str(result)}"
            print(f"[Graph] 并行执行错误: {result}")
            state["errors"].append(error_msg)
    
    duration = (datetime.now() - start).total_seconds()
    print(f"[Graph] 并行分析完成，总耗时: {duration:.2f}秒")
    
    # 打印各分析结果状态
    print(f"  - 文献分析: {'✓' if state.get('literature_result') else '✗'}")
    print(f"  - 临床分析: {'✓' if state.get('clinical_result') else '✗'}")
    print(f"  - 专利分析: {'✓' if state.get('patent_result') else '✗'}")
    print(f"  - 商业分析: {'✓' if state.get('commercial_result') else '✗'}")
    
    return state

async def editor_node(state: AnalysisState) -> AnalysisState:
    """编辑器节点 - 生成最终报告"""
    try:
        print(f"[Graph] 开始生成报告")
        start = datetime.now()
        
        # 收集所有成功的分析结果
        agents_results = {}
        
        if state.get("literature_result"):
            agents_results["literature"] = state["literature_result"]
            print("  - 包含文献分析结果")
            
        if state.get("clinical_result"):
            agents_results["clinical"] = state["clinical_result"]
            print("  - 包含临床分析结果")
            
        if state.get("patent_result"):
            agents_results["patent"] = state["patent_result"]
            print("  - 包含专利分析结果")
            
        if state.get("commercial_result"):
            agents_results["commercial"] = state["commercial_result"]
            print("  - 包含商业分析结果")
        
        # 检查是否有足够的结果
        if not agents_results:
            raise Exception("没有可用的分析结果")
        
        print(f"  共有 {len(agents_results)} 个分析结果")
        
        # 生成报告
        report = editor_expert.generate_report(
            agents_results=agents_results,
            gene_name=state["gene_name"]
        )
        
        state["final_report"] = report
        state["status"] = "completed"
        state["end_time"] = datetime.now()
        
        # 计算总执行时间
        if state.get("start_time"):
            state["execution_time"] = (state["end_time"] - state["start_time"]).total_seconds()
        
        duration = (datetime.now() - start).total_seconds()
        print(f"[Graph] 报告生成完成，耗时: {duration:.2f}秒")
        
    except Exception as e:
        error_msg = f"Report generation failed: {str(e)}"
        print(f"[Graph] 报告生成失败: {e}")
        state["errors"].append(error_msg)
        state["status"] = "failed"
        state["final_report"] = None
        state["end_time"] = datetime.now()
    
    return state

# ============ 图构建函数 ============

def build_parallel_graph() -> StateGraph:
    """构建并行执行图"""
    print("[Graph] 构建并行执行图")
    
    # 创建状态图
    graph = StateGraph(AnalysisState)
    
    # 添加节点
    graph.add_node("init", init_node)
    graph.add_node("parallel_analysis", parallel_analysis_node)
    graph.add_node("editor", editor_node)
    
    # 设置入口点
    graph.set_entry_point("init")
    
    # 添加边（执行流程）
    graph.add_edge("init", "parallel_analysis")
    graph.add_edge("parallel_analysis", "editor")
    graph.add_edge("editor", END)
    
    print("[Graph] 并行图构建完成: init → parallel_analysis → editor → END")
    
    return graph

def build_serial_graph() -> StateGraph:
    """构建串行执行图"""
    print("[Graph] 构建串行执行图")
    
    # 创建状态图
    graph = StateGraph(AnalysisState)
    
    # 添加所有节点
    graph.add_node("init", init_node)
    graph.add_node("literature", literature_node)
    graph.add_node("clinical", clinical_node)
    graph.add_node("patent", patent_node)
    graph.add_node("commercial", commercial_node)
    graph.add_node("editor", editor_node)
    
    # 设置入口点
    graph.set_entry_point("init")
    
    # 添加边（串行执行）
    graph.add_edge("init", "literature")
    graph.add_edge("literature", "clinical")
    graph.add_edge("clinical", "patent")
    graph.add_edge("patent", "commercial")
    graph.add_edge("commercial", "editor")
    graph.add_edge("editor", END)
    
    print("[Graph] 串行图构建完成: init → literature → clinical → patent → commercial → editor → END")
    
    return graph