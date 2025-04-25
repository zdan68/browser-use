"""
任务定义模块，包含所有拆分的任务描述，从Markdown文件中加载
"""
import os
from typing import Dict, List, Any
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 任务顺序列表
TASK_SEQUENCE = [
    "login",
    # "baidu",
    # "zhihu",
    # "google",
    "step1_understand",
    "step2_analyze_passage",
    "step3_analyze_context",
    "step4_judge_reason",
    "step5_make_choice",
    # "check_result",
    # "evaluation"
]

# 任务名称映射
TASK_NAMES = {
    "login": "登录",
    "baidu": "百度",
    "zhihu": "知乎",
    "google": "谷歌",
    "step1_understand": "完成步骤1 - 理解任务",
    "step2_analyze_passage": "完成步骤2 - 分析插入段落",
    "step3_analyze_context": "完成步骤3 - 分析选项C位置的上下文",
    "step4_judge_reason": "完成步骤4 - 判断与说明理由",
    "step5_make_choice": "完成步骤5 - 做出选择",
    "check_result": "查看结果并结束",
    "evaluation": "总结评估"
}

# 获取任务文件夹路径
def get_tasks_dir() -> Path:
    """
    获取任务文件夹的路径
    
    Returns:
        Path对象，指向任务文件夹
    """
    # 改为直接使用当前目录下的tasks文件夹
    root_dir = Path(__file__).parent
    tasks_dir = root_dir / "tasks"
    return tasks_dir

def read_task_description(task_key: str) -> str:
    """
    从Markdown文件中读取任务描述
    
    Args:
        task_key: 任务的键名
    Returns:
        任务描述文本
    """
    tasks_dir = get_tasks_dir()
    task_file = tasks_dir / f"{task_key}.md"
    
    try:
        with open(task_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"任务文件 {task_key}.md 不存在"

def read_report_template() -> str:
    """
    读取报告模板
    
    Returns:
        报告模板文本
    """
    tasks_dir = get_tasks_dir()
    template_file = tasks_dir / "report_template.md"
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""

def get_task(task_key: str) -> Dict[str, Any]:
    """
    获取指定任务的详细信息
    
    Args:
        task_key: 任务的键名
    Returns:
        任务信息字典
    """
    description = read_task_description(task_key)
    name = TASK_NAMES.get(task_key, "未知任务")
    
    return {
        "name": name,
        "description": description
    }

def get_report_template() -> str:
    """
    获取报告模板
    
    Returns:
        报告模板字符串
    """
    return ""
