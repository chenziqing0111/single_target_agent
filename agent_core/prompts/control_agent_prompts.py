# agent_core/prompts/control_agent_prompts.py

def get_task_description_prompt(history: str, user_input: str) -> str:
    """生成任务解析的 prompt，让 LLM 分析并返回任务"""
    return f"""
    {history}
    用户输入：{user_input}

    请分析用户输入，识别其中涉及的任务。返回的格式应为一个任务列表，每个任务包含名称和描述。任务名称应为 '疾病'、'靶点'、'竞争'，任务描述应简要说明任务的内容。
    示例任务：
    [{'task_name': '疾病', 'description': '与疾病相关的靶点研究'},
     {'task_name': '靶点', 'description': '靶点研究'},
     {'task_name': '竞争信息', 'description': '竞争对手分析'}]

    返回识别出的任务列表，例如：
    [{'task_name': '疾病', 'description': '与疾病相关的靶点研究'},
     {'task_name': '靶点', 'description': '靶点研究'}]
    """
