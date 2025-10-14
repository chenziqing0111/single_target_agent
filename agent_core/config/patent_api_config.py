# agent_core/config/patent_api_config.py
# 专利API配置管理 - 真实数据源配置验证

import os
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

def validate_patent_api_config() -> Tuple[List[str], List[str], Dict[str, str]]:
    """
    验证专利API配置
    
    Returns:
        - available_apis: 可用的API列表
        - missing_configs: 缺失的配置列表  
        - status_details: 详细状态信息
    """
    
    api_configs = {
        'patentsview': {
            'env_var': 'PATENTSVIEW_API_KEY',
            'name': 'PatentsView API',
            'url': 'https://search.patentsview.org',
            'description': '美国专利数据库API'
        },
        'uspto': {
            'env_var': 'USPTO_API_KEY', 
            'name': 'USPTO API',
            'url': 'https://developer.uspto.gov',
            'description': '美国专利商标局官方API'
        },
        'google': {
            'env_var': None,  # Google Patents 不需要API密钥
            'name': 'Google Patents',
            'url': 'https://patents.google.com',
            'description': 'Google专利搜索（网页抓取）'
        },
        'wipo': {
            'env_var': None,  # WIPO PatentScope 不需要API密钥
            'name': 'WIPO PatentScope',
            'url': 'https://patentscope.wipo.int',
            'description': '世界知识产权组织专利数据库'
        }
    }
    
    available_apis = []
    missing_configs = []
    status_details = {}
    
    logger.info("🔍 开始验证专利API配置...")
    
    for api_name, config in api_configs.items():
        env_var = config['env_var']
        
        if env_var is None:
            # 不需要API密钥的服务
            available_apis.append(api_name)
            status_details[api_name] = f"✅ {config['name']}: 可用（无需API密钥）"
            logger.info(f"✅ {config['name']}: 可用（无需API密钥）")
        else:
            # 需要API密钥的服务
            api_key = os.getenv(env_var)
            if api_key and len(api_key.strip()) > 0:
                available_apis.append(api_name)
                status_details[api_name] = f"✅ {config['name']}: 已配置API密钥"
                logger.info(f"✅ {config['name']}: 已配置API密钥")
            else:
                missing_configs.append(f"{env_var} (用于 {config['name']})")
                status_details[api_name] = f"❌ {config['name']}: 缺少API密钥 ({env_var})"
                logger.warning(f"❌ {config['name']}: 缺少API密钥 ({env_var})")
    
    # 汇总报告
    total_apis = len(api_configs)
    available_count = len(available_apis)
    
    logger.info(f"📊 专利API配置验证完成: {available_count}/{total_apis} 个API可用")
    
    if available_count == 0:
        logger.error("⚠️ 警告: 没有可用的专利数据源！系统将无法获取真实专利数据")
    elif available_count < total_apis:
        logger.warning(f"⚠️ 注意: 只有 {available_count}/{total_apis} 个专利API可用，数据覆盖可能有限")
    else:
        logger.info("🎉 所有专利API配置完成！")
    
    return available_apis, missing_configs, status_details

def get_api_setup_instructions() -> str:
    """获取API设置说明"""
    return """
🔧 专利API配置说明:

1. PatentsView API (推荐):
   - 注册: https://search.patentsview.org
   - 环境变量: PATENTSVIEW_API_KEY
   - 特点: 免费，高质量美国专利数据

2. USPTO API:
   - 注册: https://developer.uspto.gov
   - 环境变量: USPTO_API_KEY  
   - 特点: 官方API，权威数据

3. Google Patents:
   - 无需注册
   - 特点: 网页抓取，全球专利覆盖

4. WIPO PatentScope:
   - 无需注册
   - 特点: 国际专利数据

设置方法:
export PATENTSVIEW_API_KEY="your_key_here"
export USPTO_API_KEY="your_key_here"

或在 .env 文件中:
PATENTSVIEW_API_KEY=your_key_here
USPTO_API_KEY=your_key_here
"""

def check_minimum_requirements() -> bool:
    """检查是否满足最低配置要求"""
    available_apis, _, _ = validate_patent_api_config()
    
    # 至少需要一个可用的API
    if len(available_apis) >= 1:
        logger.info("✅ 满足最低专利API配置要求")
        return True
    else:
        logger.error("❌ 不满足最低专利API配置要求 - 至少需要一个可用的API")
        return False

if __name__ == "__main__":
    print("🔍 专利API配置验证工具")
    print("=" * 50)
    
    available_apis, missing_configs, status_details = validate_patent_api_config()
    
    print("\n📋 API状态详情:")
    for api_name, status in status_details.items():
        print(f"  {status}")
    
    if missing_configs:
        print(f"\n⚠️ 缺失的配置:")
        for config in missing_configs:
            print(f"  - {config}")
        print(get_api_setup_instructions())
    
    print(f"\n✅ 可用API: {available_apis}")
    print(f"❌ 缺失配置: {len(missing_configs)} 项")
    
    if check_minimum_requirements():
        print("🎉 系统可以正常运行！")
    else:
        print("⚠️ 系统无法获取真实专利数据，请配置至少一个API")