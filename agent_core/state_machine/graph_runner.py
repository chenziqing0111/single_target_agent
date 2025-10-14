"""
Graph Runner - 图执行器
负责编译和执行LangGraph图
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

from agent_core.state_machine.graph_definition import (
    build_parallel_graph,
    build_serial_graph,
    initialize_experts,
    AnalysisState
)

class GraphRunner:
    """图执行器 - 负责运行分析流程"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化GraphRunner
        
        Args:
            config: 配置字典，包含:
                - parallel: bool, 是否并行执行
                - timeout: int, 超时时间（秒）
                - openai_api_key: str, OpenAI API密钥
                - company_name: str, 公司名称
        """
        self.config = config or {}
        
        # 确保必要的配置
        self._ensure_config()
        
        # 执行配置
        self.timeout = self.config.get("timeout", 1800)  # 默认30分钟
        self.parallel = self.config.get("parallel", True)  # 默认并行
        
        # 初始化专家（传递配置）
        print(f"[Runner] 初始化GraphRunner")
        print(f"  - 执行模式: {'并行' if self.parallel else '串行'}")
        print(f"  - 超时时间: {self.timeout}秒")
        
        initialize_experts(self.config)
        
        # 缓存编译后的图
        self._compiled_graphs = {}
    
    def _ensure_config(self):
        """确保配置包含必要的项"""
        defaults = {
            'openai_api_key': 'sk-9b3ad78d6d51431c90091b575072e62f',
            'openai_base_url': 'https://api.deepseek.com',
            'zhihuiya_api_key': 'fh10ixx8marmhm9kbl3cx5676qn8nshcuwtktz0b05ebl7qf',
            'zhihuiya_credentials': '74z26dxne81bnmrbd8vjwt7r8fc6tr6cxxdvapslbz4knycxknv3dnjprap6igjy',
            'company_name': '益杰立科',
            'parallel': True,
            'timeout': 1800
        }
        
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value
    
    def _get_compiled_graph(self, parallel: bool):
        """获取编译后的图（带缓存）"""
        cache_key = f"{'parallel' if parallel else 'serial'}"
        
        if cache_key not in self._compiled_graphs:
            print(f"[Runner] 编译{cache_key}图...")
            
            if parallel:
                graph = build_parallel_graph()
            else:
                graph = build_serial_graph()
            
            self._compiled_graphs[cache_key] = graph.compile()
            print(f"[Runner] {cache_key}图编译完成")
        
        return self._compiled_graphs[cache_key]
    
    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行分析图
        
        Args:
            initial_state: 初始状态，必须包含:
                - gene_name: str, 基因名称
                - mode: str, 分析模式（默认"deep"）
                - parallel: bool, 是否并行（可选，覆盖默认配置）
        
        Returns:
            最终状态字典，包含:
                - final_report: str, 最终HTML报告
                - status: str, 执行状态
                - errors: list, 错误列表
                - execution_time: float, 执行时间
        """
        start_time = datetime.now()
        
        # 验证输入
        if not initial_state.get("gene_name"):
            return {
                "status": "failed",
                "errors": ["Missing gene_name in initial state"],
                "final_report": None
            }
        
        gene_name = initial_state["gene_name"]
        mode = initial_state.get("mode", "deep")
        parallel = initial_state.get("parallel", self.parallel)
        
        print(f"\n{'='*60}")
        print(f"[Runner] 开始执行分析")
        print(f"  - 基因: {gene_name}")
        print(f"  - 模式: {mode}")
        print(f"  - 执行: {'并行' if parallel else '串行'}")
        print(f"  - 时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        try:
            # 获取编译后的图
            app = self._get_compiled_graph(parallel)
            
            # 创建初始状态
            state = {
                "gene_name": gene_name,
                "mode": mode,
                "parallel": parallel,
                "literature_result": None,
                "clinical_result": None,
                "patent_result": None,
                "commercial_result": None,
                "final_report": None,
                "errors": [],
                "status": "initialized",
                "start_time": start_time,
                "end_time": None,
                "execution_time": None
            }
            
            # 执行图（带超时控制）
            print(f"[Runner] 执行分析图，超时限制: {self.timeout}秒")
            
            result = await asyncio.wait_for(
                app.ainvoke(state),
                timeout=self.timeout
            )
            
            # 计算总执行时间
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 更新结果
            result["execution_time"] = duration
            result["execution_mode"] = "parallel" if parallel else "serial"
            
            # 打印执行结果摘要
            print(f"\n{'='*60}")
            print(f"[Runner] 执行完成")
            print(f"  - 状态: {result.get('status', 'unknown')}")
            print(f"  - 耗时: {duration:.2f}秒")
            print(f"  - 错误: {len(result.get('errors', []))}个")
            
            if result.get('final_report'):
                report_size = len(result['final_report']) / 1024
                print(f"  - 报告: {report_size:.2f}KB")
            else:
                print(f"  - 报告: 未生成")
            
            print(f"{'='*60}\n")
            
            return result
            
        except asyncio.TimeoutError:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"\n[Runner] ⚠️ 执行超时 (已运行{duration:.0f}秒，超过{self.timeout}秒限制)")
            
            return {
                "status": "timeout",
                "errors": [f"Analysis timeout after {self.timeout} seconds"],
                "final_report": None,
                "execution_time": duration,
                "gene_name": gene_name
            }
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            print(f"\n[Runner] ❌ 执行失败")
            print(f"  - 错误: {error_msg}")
            print(f"  - 追踪:\n{traceback.format_exc()}")
            
            return {
                "status": "failed",
                "errors": [error_msg],
                "final_report": None,
                "execution_time": duration,
                "gene_name": gene_name
            }
    
    def set_parallel_mode(self, parallel: bool):
        """动态设置并行/串行模式"""
        self.parallel = parallel
        mode_str = "并行" if parallel else "串行"
        print(f"[Runner] 切换到{mode_str}模式")
    
    def set_timeout(self, timeout: int):
        """动态设置超时时间"""
        self.timeout = timeout
        print(f"[Runner] 设置超时时间: {timeout}秒")
    
    def get_config(self) -> Dict:
        """获取当前配置"""
        return {
            "parallel": self.parallel,
            "timeout": self.timeout,
            "config": self.config
        }


# ============ 测试函数 ============

async def test_graph_runner():
    """测试GraphRunner"""
    
    print("="*60)
    print("GraphRunner 测试")
    print("="*60)
    
    # 测试配置
    config = {
        "parallel": True,  # 先测试并行
        "timeout": 300,    # 5分钟超时（测试用）
        "company_name": "益杰立科"
    }
    
    # 创建Runner
    runner = GraphRunner(config)
    
    # 测试基因
    test_gene = "IL17RA"
    
    # 准备初始状态
    initial_state = {
        "gene_name": test_gene,
        "mode": "deep",
        "parallel": True
    }
    
    print(f"\n开始测试分析: {test_gene}")
    print("-"*40)
    
    # 执行分析
    result = await runner.run(initial_state)
    
    # 打印结果
    print("\n" + "="*60)
    print("测试结果")
    print("="*60)
    print(f"状态: {result.get('status')}")
    print(f"执行时间: {result.get('execution_time', 0):.2f}秒")
    print(f"错误数量: {len(result.get('errors', []))}")
    
    if result.get('errors'):
        print("\n错误列表:")
        for i, error in enumerate(result['errors'], 1):
            print(f"  {i}. {error}")
    
    if result.get('final_report'):
        # 保存报告
        filename = f"test_{test_gene}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(result['final_report'])
        print(f"\n报告已保存: {filename}")
    else:
        print("\n未生成报告")
    
    print("\n测试完成！")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_graph_runner())