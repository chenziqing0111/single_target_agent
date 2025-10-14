# /prompt/prompts.py

def format_markdown_section(title: str, content: str) -> str:
    return f"""
## {title}

{content.strip()}
""".strip()


def format_reference_list(pmid_list: list[str]) -> str:
    if not pmid_list:
        return "\n> 参考文献：暂无可提取 PMID。"
    return "\n> 参考文献：" + ", ".join([f"PMID:{pmid}" for pmid in pmid_list])
