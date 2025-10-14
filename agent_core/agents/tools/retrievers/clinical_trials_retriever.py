# agent_core/agents/tools/retrievers/clinical_trials_retriever.py
# 修复版临床试验检索器 - 处理API返回的字符串数据

import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional
from urllib.parse import urlencode
import logging
from datetime import datetime

# Cookie警告修复
import warnings
warnings.filterwarnings("ignore", message=".*Invalid attribute.*")
warnings.filterwarnings("ignore", message=".*Can not load response cookies.*")
logging.getLogger('aiohttp').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

class ClinicalTrialsRetriever:
    """专门的临床试验检索器 - 修复版"""
    
    def __init__(self):
        self.name = "ClinicalTrials Retriever"
        self.version = "2.2.0"
        self.base_url = "https://beta.clinicaltrials.gov/api/v2/studies"
        self.session = None
        self.sleep_sec = 0.3
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            headers={
                'User-Agent': 'EpigenicAI/2.2.0',
                'Accept': 'application/json'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_by_gene(self, gene: str = None, **kwargs) -> List[Dict[str, Any]]:
        """根据基因名称搜索临床试验"""
        
        # 处理参数冲突
        if gene is None and 'gene' in kwargs:
            gene = kwargs.pop('gene')
        elif 'gene' in kwargs:
            kwargs.pop('gene')
            
        if not gene:
            logger.warning("基因名称为空")
            return []
        
        if not self.session:
            self.session = aiohttp.ClientSession(
                cookie_jar=aiohttp.DummyCookieJar(),
                headers={
                    'User-Agent': 'EpigenicAI/2.2.0',
                    'Accept': 'application/json'
                }
            )
        
        try:
            trials = await self._search_trials_v2(gene, **kwargs)
            logger.info(f"为基因 {gene} 找到 {len(trials)} 个临床试验")
            return trials
            
        except Exception as e:
            logger.error(f"搜索基因 {gene} 的临床试验时出错: {str(e)}")
            return []
    
    async def _search_trials_v2(self, term: str, **kwargs) -> List[Dict[str, Any]]:
        """使用新版API v2搜索试验 - 增强搜索覆盖"""
        
        page_size = kwargs.get('page_size', 50)  # 增加默认页面大小
        max_pages = kwargs.get('max_pages', 10)  # 增加默认搜索深度
        
        all_studies = []
        unique_nct_ids = set()  # 用于去重
        
        # 多字段搜索策略
        search_configs = self._build_search_configs(term, kwargs)
        
        for config_idx, base_params in enumerate(search_configs):
            logger.info(f"执行搜索配置 {config_idx + 1}/{len(search_configs)}: {base_params}")
            
            page_token = None
            
            for page in range(max_pages):
                params = base_params.copy()
                params.update({
                    "pageSize": page_size,
                    "format": "json"
                })
                
                if page_token:
                    params["pageToken"] = page_token
            
                # 添加过滤条件
                if kwargs.get('condition'):
                    params["query.cond"] = kwargs['condition']
                if kwargs.get('phase'):
                    params["filter.phase"] = kwargs['phase']
                if kwargs.get('status'):
                    params["filter.overallStatus"] = kwargs['status']
                
                try:
                    async with self.session.get(self.base_url, params=params, timeout=30) as response:
                        if response.status == 200:
                            data = await response.json()
                            studies = data.get("studies", [])
                            
                            logger.info(f"配置{config_idx+1} 第{page+1}页获取到 {len(studies)} 个试验")
                            
                            if studies:
                                # 解析每个试验，增强错误处理和去重
                                for i, study in enumerate(studies):
                                    try:
                                        parsed_study = self._parse_study_v2_enhanced(study)
                                        nct_id = parsed_study.get("nct_id")
                                        
                                        # 只添加有效且未重复的试验
                                        if nct_id and nct_id not in unique_nct_ids:
                                            unique_nct_ids.add(nct_id)
                                            all_studies.append(parsed_study)
                                            
                                    except Exception as e:
                                        logger.warning(f"配置{config_idx+1} 第{page+1}页 试验{i+1} 解析失败: {str(e)}")
                                        # 不使用任何模拟数据，直接跳过解析失败的试验
                                        continue
                                
                                logger.info(f"配置{config_idx+1} 第{page+1}页成功解析 {len([s for s in all_studies if s.get('nct_id') in unique_nct_ids])} 个试验")
                            
                            # 获取下一页token
                            page_token = data.get("nextPageToken")
                            if not page_token:
                                break
                                
                        else:
                            logger.error(f"API请求失败: HTTP {response.status}")
                            try:
                                error_text = await response.text()
                                logger.error(f"错误响应: {error_text[:500]}")
                            except:
                                pass
                            break
                        
                except Exception as e:
                    logger.error(f"第{page+1}页请求失败: {str(e)}")
                    break
                
                # 请求间隔
                if page < max_pages - 1:
                    await asyncio.sleep(self.sleep_sec)
        
        logger.info(f"总共获取到 {len(all_studies)} 个试验")
        return all_studies
    
    def _build_search_configs(self, term: str, kwargs: Dict) -> List[Dict[str, str]]:
        """构建多字段搜索配置"""
        
        search_configs = []
        
        # 基础搜索 - 在所有字段中搜索
        search_configs.append({"query.term": term})
        
        # 标题搜索
        search_configs.append({"query.titles": term})
        
        # 条件搜索
        search_configs.append({"query.cond": term})
        
        # 干预措施搜索
        search_configs.append({"query.intr": term})
        
        # 如果是基因名，还要尝试其他可能的写法
        if len(term) <= 10 and term.isalpha():  # 可能是基因名
            # 尝试全大写
            if term != term.upper():
                search_configs.append({"query.term": term.upper()})
            
            # 尝试全小写
            if term != term.lower():
                search_configs.append({"query.term": term.lower()})
        
        return search_configs
    
    def _parse_study_v2_enhanced(self, study: Any) -> Dict[str, Any]:
        """增强版试验数据解析 - 更好的错误处理"""
        
        try:
            # 检查数据类型和格式
            if isinstance(study, str):
                logger.warning(f"试验数据是字符串，尝试解析JSON: {study[:100]}...")
                try:
                    study = json.loads(study)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {str(e)}")
                    # 不使用任何模拟数据，返回错误标识
                    raise ValueError(f"无法解析JSON格式的试验数据: {str(e)}")
            
            if not isinstance(study, dict):
                logger.error(f"试验数据不是字典类型: {type(study)}")
                raise ValueError(f"试验数据类型错误: {type(study)}")
            
            # 获取protocolSection - 增强错误处理
            protocol = study.get("protocolSection")
            if not protocol:
                logger.warning("试验数据缺少protocolSection")
                raise ValueError("试验数据缺少protocolSection")
            
            if not isinstance(protocol, dict):
                logger.error(f"protocolSection不是字典类型: {type(protocol)}")
                raise ValueError(f"protocolSection类型错误: {type(protocol)}")
            
            # 安全提取各个模块
            ident = protocol.get("identificationModule", {})
            desc = protocol.get("descriptionModule", {})
            design = protocol.get("designModule", {})
            status = protocol.get("statusModule", {})
            sponsor = protocol.get("sponsorCollaboratorsModule", {})
            conditions = protocol.get("conditionsModule", {})
            interventions = protocol.get("armsInterventionsModule", {})
            
            # 确保关键字段存在
            nct_id = ident.get("nctId", "") if isinstance(ident, dict) else ""
            if not nct_id:
                logger.error("缺少NCT ID")
                raise ValueError("缺少NCT ID")
            
            # 构建解析结果
            parsed = {
                "nct_id": nct_id,
                "title": ident.get("briefTitle", "") if isinstance(ident, dict) else "",
                "status": self._extract_status_v2_safe(status),
                "phase": self._extract_phase_v2_safe(design),
                "lead_sponsor": self._extract_sponsor_v2_safe(sponsor),
                "condition": self._extract_conditions_v2_safe(conditions),
                "interventions": self._extract_interventions_v2_safe(interventions),
                "enrollment": self._extract_enrollment_v2_safe(design),
                "start_date": self._extract_start_date_v2_safe(status),
                "completion_date": self._extract_completion_date_v2_safe(status),
                "outcomes": self._extract_outcomes_v2_safe(protocol),
                "study_design": self._extract_study_design_v2_safe(design),
                "locations": self._extract_locations_v2_safe(protocol.get("contactsLocationsModule", {})),
                "brief_summary": self._extract_brief_summary_v2_safe(desc),
                "detailed_description": self._extract_detailed_description_v2_safe(desc)
            }
            
            return parsed
            
        except Exception as e:
            # 不使用任何模拟数据，直接抛出异常
            logger.error(f"解析试验数据时出错: {str(e)}")
            raise ValueError(f"试验数据解析失败: {str(e)}")
    
    # 增强版安全提取方法
    def _extract_status_v2_safe(self, status: Any) -> str:
        """安全提取试验状态"""
        if not isinstance(status, dict):
            return "Unknown"
        return status.get("overallStatus", "Unknown")
    
    def _extract_phase_v2_safe(self, design: Any) -> str:
        """安全提取试验阶段"""
        if not isinstance(design, dict):
            return "Unknown"
        
        phases = design.get("phases", [])
        if phases and isinstance(phases, list):
            phase_mapping = {
                "EARLY_PHASE1": "Early Phase 1",
                "PHASE1": "Phase 1",
                "PHASE2": "Phase 2", 
                "PHASE3": "Phase 3",
                "PHASE4": "Phase 4"
            }
            
            if len(phases) > 1:
                phase_order = {"EARLY_PHASE1": 0, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4}
                max_phase = max(phases, key=lambda x: phase_order.get(x, -1))
                return phase_mapping.get(max_phase, max_phase)
            else:
                return phase_mapping.get(phases[0], phases[0])
        
        study_type = design.get("studyType", "")
        if study_type == "INTERVENTIONAL":
            return "Phase 2"
        elif study_type == "OBSERVATIONAL":
            return "Observational"
        
        return "Unknown"
    
    def _extract_sponsor_v2_safe(self, sponsor: Any) -> str:
        """安全提取主要发起方"""
        if not isinstance(sponsor, dict):
            return "Unknown"
        lead_sponsor = sponsor.get("leadSponsor", {})
        if not isinstance(lead_sponsor, dict):
            return "Unknown"
        return lead_sponsor.get("name", "Unknown")
    
    def _extract_conditions_v2_safe(self, conditions: Any) -> str:
        """安全提取适应症"""
        if not isinstance(conditions, dict):
            return "Unknown"
        conditions_list = conditions.get("conditions", [])
        if conditions_list and isinstance(conditions_list, list):
            return "; ".join(conditions_list[:3])
        return "Unknown"
    
    def _extract_interventions_v2_safe(self, interventions: Any) -> List[Dict]:
        """安全提取干预措施"""
        if not isinstance(interventions, dict):
            return []
        interventions_list = interventions.get("interventions", [])
        if not isinstance(interventions_list, list):
            return []
        
        result = []
        for intervention in interventions_list:
            if isinstance(intervention, dict):
                result.append({
                    "name": intervention.get("name", ""),
                    "type": intervention.get("type", ""),
                    "description": intervention.get("description", "")
                })
        return result
    
    def _extract_enrollment_v2_safe(self, design: Any) -> Dict:
        """安全提取入组人数"""
        if not isinstance(design, dict):
            return {"count": 0, "type": "Unknown"}
        
        enrollment_info = design.get("enrollmentInfo", {})
        if not isinstance(enrollment_info, dict):
            return {"count": 0, "type": "Unknown"}
        
        count = enrollment_info.get("count", 0)
        enrollment_type = enrollment_info.get("type", "Actual")
        
        if isinstance(count, str):
            try:
                count = int(count)
            except ValueError:
                count = 0
        elif not isinstance(count, int):
            count = 0
        
        return {"count": count, "type": enrollment_type}
    
    def _extract_start_date_v2_safe(self, status: Any) -> str:
        """安全提取开始日期"""
        if not isinstance(status, dict):
            return ""
        start_date = status.get("startDateStruct", {})
        if not isinstance(start_date, dict):
            return ""
        return start_date.get("date", "")
    
    def _extract_completion_date_v2_safe(self, status: Any) -> str:
        """安全提取完成日期"""
        if not isinstance(status, dict):
            return ""
        completion_date = status.get("completionDateStruct", {})
        if not isinstance(completion_date, dict):
            return ""
        return completion_date.get("date", "")
    
    def _extract_outcomes_v2_safe(self, protocol: Any) -> List[Dict]:
        """安全提取主要终点"""
        if not isinstance(protocol, dict):
            return []
        
        outcomes_module = protocol.get("outcomesModule", {})
        if not isinstance(outcomes_module, dict):
            return []
        
        primary_outcomes = outcomes_module.get("primaryOutcomes", [])
        if not isinstance(primary_outcomes, list):
            return []
        
        result = []
        for outcome in primary_outcomes:
            if isinstance(outcome, dict):
                result.append({
                    "type": "Primary",
                    "measure": outcome.get("measure", ""),
                    "description": outcome.get("description", "")
                })
        return result
    
    def _extract_study_design_v2_safe(self, design: Any) -> str:
        """安全提取研究设计"""
        if not isinstance(design, dict):
            return "Unknown"
        
        study_type = design.get("studyType", "")
        if study_type == "INTERVENTIONAL":
            design_info = design.get("designInfo", {})
            if isinstance(design_info, dict):
                allocation = design_info.get("allocation", "")
                intervention_model = design_info.get("interventionModel", "")
                
                design_parts = []
                if allocation:
                    design_parts.append(allocation)
                if intervention_model:
                    design_parts.append(intervention_model)
                
                return ", ".join(design_parts) if design_parts else "Interventional"
        
        return study_type if study_type else "Unknown"
    
    def _extract_locations_v2_safe(self, contacts: Any) -> List[str]:
        """安全提取试验地点"""
        if not isinstance(contacts, dict):
            return ["Location not specified"]
        
        locations = contacts.get("locations", [])
        if not isinstance(locations, list):
            return ["Location not specified"]
        
        location_list = []
        for location in locations:
            if isinstance(location, dict):
                facility = location.get("facility", {})
                city = location.get("city", "")
                country = location.get("country", "")
                
                if isinstance(facility, dict) and facility.get("name"):
                    location_str = facility["name"]
                    if city:
                        location_str += f", {city}"
                    if country:
                        location_str += f", {country}"
                    location_list.append(location_str)
        
        return location_list[:5] if location_list else ["Location not specified"]
    
    def _extract_brief_summary_v2_safe(self, desc: Any) -> str:
        """安全提取简要总结"""
        if not isinstance(desc, dict):
            return ""
        return desc.get("briefSummary", "")
    
    def _extract_detailed_description_v2_safe(self, desc: Any) -> str:
        """安全提取详细描述"""
        if not isinstance(desc, dict):
            return ""
        return desc.get("detailedDescription", "")
    
    def _parse_study_v2(self, study: Any) -> Dict[str, Any]:
        """解析新版API v2的试验数据 - 修复版"""
        
        try:
            # 检查数据类型
            if isinstance(study, str):
                logger.warning(f"试验数据是字符串，尝试解析JSON: {study[:100]}...")
                try:
                    study = json.loads(study)
                except json.JSONDecodeError:
                    logger.error("无法解析JSON格式的试验数据")
                    return {"nct_id": "", "title": "JSON Parse Error", "status": "Unknown"}
            
            if not isinstance(study, dict):
                logger.error(f"试验数据不是字典类型: {type(study)}")
                return {"nct_id": "", "title": "Type Error", "status": "Unknown"}
            
            # 获取protocolSection
            protocol = study.get("protocolSection", {})
            if not protocol:
                logger.warning("试验数据缺少protocolSection")
                return {"nct_id": "", "title": "Missing Protocol", "status": "Unknown"}
            
            # 各个模块
            ident = protocol.get("identificationModule", {})
            desc = protocol.get("descriptionModule", {})
            design = protocol.get("designModule", {})
            status = protocol.get("statusModule", {})
            sponsor = protocol.get("sponsorCollaboratorsModule", {})
            conditions = protocol.get("conditionsModule", {})
            interventions = protocol.get("armsInterventionsModule", {})
            
            # 提取基本信息
            parsed = {
                "nct_id": ident.get("nctId", ""),
                "title": ident.get("briefTitle", ""),
                "status": self._extract_status_v2(status),
                "phase": self._extract_phase_v2(design),
                "lead_sponsor": self._extract_sponsor_v2(sponsor),
                "condition": self._extract_conditions_v2(conditions),
                "interventions": self._extract_interventions_v2(interventions),
                "enrollment": self._extract_enrollment_v2(design),
                "start_date": self._extract_start_date_v2(status),
                "completion_date": self._extract_completion_date_v2(status),
                "outcomes": self._extract_outcomes_v2(protocol),
                "study_design": self._extract_study_design_v2(design),
                "locations": self._extract_locations_v2(protocol.get("contactsLocationsModule", {})),
                "brief_summary": self._extract_brief_summary_v2(desc),
                "detailed_description": self._extract_detailed_description_v2(desc)
            }
            
            return parsed
            
        except Exception as e:
            logger.error(f"解析试验数据时出错: {str(e)}")
            return {"nct_id": "", "title": "Parse Error", "status": "Unknown"}
    
    def _extract_status_v2(self, status: Dict) -> str:
        """提取试验状态"""
        return status.get("overallStatus", "Unknown")
    
    def _extract_phase_v2(self, design: Dict) -> str:
        """提取试验阶段"""
        # 方法1：直接从phases字段获取
        phases = design.get("phases", [])
        if phases:
            # 转换为标准格式
            phase_mapping = {
                "EARLY_PHASE1": "Early Phase 1",
                "PHASE1": "Phase 1",
                "PHASE2": "Phase 2", 
                "PHASE3": "Phase 3",
                "PHASE4": "Phase 4"
            }
            
            # 如果有多个阶段，返回最高阶段
            if len(phases) > 1:
                phase_order = {"EARLY_PHASE1": 0, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4}
                max_phase = max(phases, key=lambda x: phase_order.get(x, -1))
                return phase_mapping.get(max_phase, max_phase)
            else:
                return phase_mapping.get(phases[0], phases[0])
        
        # 方法2：从studyType推断
        study_type = design.get("studyType", "")
        if study_type == "INTERVENTIONAL":
            return "Phase 2"  # 默认推断
        elif study_type == "OBSERVATIONAL":
            return "Observational"
        
        return "Unknown"
    
    def _extract_sponsor_v2(self, sponsor: Dict) -> str:
        """提取主要发起方"""
        lead_sponsor = sponsor.get("leadSponsor", {})
        return lead_sponsor.get("name", "Unknown")
    
    def _extract_conditions_v2(self, conditions: Dict) -> str:
        """提取适应症"""
        conditions_list = conditions.get("conditions", [])
        if conditions_list:
            return "; ".join(conditions_list[:3])
        return "Unknown"
    
    def _extract_interventions_v2(self, interventions: Dict) -> List[Dict]:
        """提取干预措施"""
        interventions_list = interventions.get("interventions", [])
        result = []
        for intervention in interventions_list:
            result.append({
                "name": intervention.get("name", ""),
                "type": intervention.get("type", ""),
                "description": intervention.get("description", "")
            })
        return result
    
    def _extract_enrollment_v2(self, design: Dict) -> Dict:
        """提取入组人数"""
        enrollment_info = design.get("enrollmentInfo", {})
        count = enrollment_info.get("count", 0)
        enrollment_type = enrollment_info.get("type", "Actual")
        
        # 确保count是数字
        if isinstance(count, str):
            try:
                count = int(count)
            except ValueError:
                count = 0
        elif not isinstance(count, int):
            count = 0
        
        return {"count": count, "type": enrollment_type}
    
    def _extract_start_date_v2(self, status: Dict) -> str:
        """提取开始日期"""
        start_date = status.get("startDateStruct", {})
        return start_date.get("date", "")
    
    def _extract_completion_date_v2(self, status: Dict) -> str:
        """提取完成日期"""
        completion_date = status.get("completionDateStruct", {})
        return completion_date.get("date", "")
    
    def _extract_outcomes_v2(self, protocol: Dict) -> List[Dict]:
        """提取主要终点"""
        outcomes_module = protocol.get("outcomesModule", {})
        primary_outcomes = outcomes_module.get("primaryOutcomes", [])
        
        result = []
        for outcome in primary_outcomes:
            result.append({
                "type": "Primary",
                "measure": outcome.get("measure", ""),
                "description": outcome.get("description", "")
            })
        return result
    
    def _extract_study_design_v2(self, design: Dict) -> str:
        """提取研究设计"""
        study_type = design.get("studyType", "")
        if study_type == "INTERVENTIONAL":
            design_info = design.get("designInfo", {})
            allocation = design_info.get("allocation", "")
            intervention_model = design_info.get("interventionModel", "")
            
            design_parts = []
            if allocation:
                design_parts.append(allocation)
            if intervention_model:
                design_parts.append(intervention_model)
            
            return ", ".join(design_parts) if design_parts else "Interventional"
        
        return study_type
    
    def _extract_locations_v2(self, contacts: Dict) -> List[str]:
        """提取试验地点"""
        locations = contacts.get("locations", [])
        
        location_list = []
        for location in locations:
            facility = location.get("facility", {})
            city = location.get("city", "")
            country = location.get("country", "")
            
            if facility.get("name"):
                location_str = facility["name"]
                if city:
                    location_str += f", {city}"
                if country:
                    location_str += f", {country}"
                location_list.append(location_str)
        
        return location_list[:5] if location_list else ["Location not specified"]
    
    def _extract_brief_summary_v2(self, desc: Dict) -> str:
        """提取简要总结"""
        return desc.get("briefSummary", "")
    
    def _extract_detailed_description_v2(self, desc: Dict) -> str:
        """提取详细描述"""
        return desc.get("detailedDescription", "")
    
    def get_api_info(self) -> Dict[str, Any]:
        """获取API信息"""
        return {
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "api_version": "v2",
            "notes": "修复版 - 处理API返回的字符串数据"
        }

# 测试函数
async def test_retriever():
    """测试检索器功能"""
    
    print("🧪 测试修复版临床试验检索器")
    print("=" * 50)
    
    async with ClinicalTrialsRetriever() as retriever:
        
        # 测试PCSK9搜索
        print("\n1. 测试PCSK9搜索:")
        pcsk9_trials = await retriever.search_by_gene("PCSK9", page_size=5, max_pages=1)
        print(f"找到 {len(pcsk9_trials)} 个PCSK9试验")
        
        if pcsk9_trials:
            trial = pcsk9_trials[0]
            print(f"\n示例试验:")
            print(f"- NCT ID: {trial.get('nct_id', 'N/A')}")
            print(f"- 标题: {trial.get('title', 'N/A')}")
            print(f"- 状态: {trial.get('status', 'N/A')}")
            print(f"- 阶段: {trial.get('phase', 'N/A')}")
            print(f"- 发起方: {trial.get('lead_sponsor', 'N/A')}")
            print(f"- 适应症: {trial.get('condition', 'N/A')}")
            
            # 检查数据完整性
            print(f"\n数据完整性检查:")
            print(f"- 有效NCT ID: {'✅' if trial.get('nct_id') else '❌'}")
            print(f"- 有效标题: {'✅' if trial.get('title') else '❌'}")
            print(f"- 有效状态: {'✅' if trial.get('status') != 'Unknown' else '❌'}")
            print(f"- 有效阶段: {'✅' if trial.get('phase') != 'Unknown' else '❌'}")
            print(f"- 有效发起方: {'✅' if trial.get('lead_sponsor') != 'Unknown' else '❌'}")
            print(f"- 有效适应症: {'✅' if trial.get('condition') != 'Unknown' else '❌'}")

if __name__ == "__main__":
    asyncio.run(test_retriever())
