import json
import os
import re
from typing import List, Dict, Any, Optional, TYPE_CHECKING, ForwardRef
from pathlib import Path
import ast

# 引入views.py中的类
from browser_use.agent.views import ActionResult, AgentHistoryList

# 定义 CustomAgentHistoryList 类在开头
class CustomAgentHistoryList:
    """
    定制的AgentHistoryList类，简化版本用于处理result.txt中的数据
    这个类模拟了views.py中AgentHistoryList的关键方法
    """
    
    def __init__(self, all_results: List[ActionResult], all_model_outputs: List[Dict[str, Any]]):
        self.all_results = all_results
        self.all_model_outputs = all_model_outputs
    
    def action_results(self) -> List[ActionResult]:
        """获取所有操作结果"""
        return self.all_results
    
    def model_actions(self) -> List[Dict[str, Any]]:
        """获取所有模型操作"""
        return self.all_model_outputs
    
    def is_successful(self) -> Optional[bool]:
        """检查任务是否成功完成"""
        if self.all_results and len(self.all_results) > 0:
            last_result = self.all_results[-1]
            if last_result.is_done is True:
                return last_result.success
        return None
    
    def final_result(self) -> Optional[str]:
        """获取最终结果"""
        if self.all_results and len(self.all_results) > 0:
            last_result = self.all_results[-1]
            return last_result.extracted_content
        return None
    
    def is_done(self) -> bool:
        """检查任务是否完成"""
        if self.all_results and len(self.all_results) > 0:
            last_result = self.all_results[-1]
            return last_result.is_done is True
        return False
    
    def has_errors(self) -> bool:
        """检查是否有错误"""
        return any(result.error is not None for result in self.all_results)
    
    def urls(self) -> List[Optional[str]]:
        """获取所有访问的URL"""
        urls = []
        for output in self.all_model_outputs:
            if 'go_to_url' in output and 'url' in output['go_to_url']:
                urls.append(output['go_to_url']['url'])
            else:
                urls.append(None)
        return urls
    
    def action_names(self) -> List[str]:
        """获取所有操作名称"""
        action_names = []
        for action in self.all_model_outputs:
            actions = list(action.keys())
            if actions and actions[0] != 'interacted_element':
                action_names.append(actions[0])
        return action_names


def convert_results_to_json(input_file: str, output_dir: str) -> None:
    """
    将result.txt中的数据转换为结构化JSON并保存到指定目录，使用views.py中的类
    
    Args:
        input_file: 输入文件路径
        output_dir: 输出目录路径
    """
    # 创建输出目录(如果不存在)
    os.makedirs(output_dir, exist_ok=True)
    
    # 读取输入文件
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 直接解析AgentHistoryList对象
    agent_history_lists = parse_agent_history_lists(content)
    
    # 转换为结构化JSON
    agent_results = []
    
    for idx, agent_history in enumerate(agent_history_lists):
        # 使用AgentHistoryList类的方法获取所需数据
        task_result = {
            "id": idx + 1,
            "name": f"Task {idx + 1}",
            "all_results": [result.model_dump(exclude_none=True) for result in agent_history.action_results()],
            "all_model_outputs": agent_history.model_actions(),
            "success": agent_history.is_successful(),
            "completion_message": agent_history.final_result(),
            "total_actions": len(agent_history.action_results()),
            "errors": [result.model_dump(exclude_none=True) for result in agent_history.action_results() if result.error],
            "urls_visited": [url for url in agent_history.urls() if url],
            "is_done": agent_history.is_done(),
            "has_errors": agent_history.has_errors(),
            "action_names": agent_history.action_names()
        }
        
        agent_results.append(task_result)
    
    # 创建汇总结果
    summary = {
        "total_tasks": len(agent_results),
        "successful_tasks": sum(1 for r in agent_results if r["success"]),
        "failed_tasks": sum(1 for r in agent_results if not r["success"]),
        "total_actions": sum(r["total_actions"] for r in agent_results),
        "total_errors": sum(len(r["errors"]) for r in agent_results)
    }
    
    # 完整结果
    final_result = {
        "summary": summary,
        "tasks": agent_results
    }
    
    # 保存为JSON
    output_file = os.path.join(output_dir, "structured_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    print(f"结构化结果已保存到: {output_file}")
    
    # 额外生成每个任务的单独JSON文件
    for task in agent_results:
        task_file = os.path.join(output_dir, f"task_{task['id']}.json")
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        print(f"任务 {task['id']} 结果已保存到: {task_file}")


def parse_agent_history_lists(content: str) -> List[CustomAgentHistoryList]:
    """
    解析文本内容为自定义AgentHistoryList对象列表
    
    Args:
        content: 包含AgentHistoryList字符串表示的文本
    
    Returns:
        CustomAgentHistoryList对象列表
    """
    # 处理文本格式，移除外层括号
    content = content.strip()
    if content.startswith('[') and content.endswith(']'):
        content = content[1:-1]
    
    agent_history_lists = []
    
    # 使用正则表达式找到所有AgentHistoryList对象
    pattern = r'AgentHistoryList\(all_results=\[(.*?)\], all_model_outputs=\[(.*?)\]\)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for match in matches:
        actions_text, model_outputs_text = match
        
        # 解析ActionResult对象
        action_results = []
        action_result_pattern = r'ActionResult\((.*?)\)'
        action_matches = re.findall(action_result_pattern, actions_text, re.DOTALL)
        
        for action_match in action_matches:
            # 提取ActionResult的参数，确保include_in_memory是布尔值
            is_done = extract_param(action_match, 'is_done', default=False)
            success = extract_param(action_match, 'success')  # 可以是None
            extracted_content = extract_string_param(action_match, 'extracted_content')
            error = extract_string_param(action_match, 'error')
            
            # 关键修复：始终提供布尔值 - 如果找不到或为None，默认为False
            include_in_memory = extract_param(action_match, 'include_in_memory', default=False)
            if include_in_memory is None:
                include_in_memory = False
            
            # 创建ActionResult对象
            action_result = ActionResult(
                is_done=is_done,
                success=success,
                extracted_content=extracted_content,
                error=error,
                include_in_memory=include_in_memory  # 确保是布尔值
            )
            
            action_results.append(action_result)
        
        # 解析model_outputs
        model_outputs = parse_model_outputs(model_outputs_text)
        
        # 创建一个自定义的AgentHistoryList
        custom_agent_history = CustomAgentHistoryList(action_results, model_outputs)
        agent_history_lists.append(custom_agent_history)
    
    return agent_history_lists


def extract_param(text: str, param_name: str, default: Any = None) -> Any:
    """
    从文本中提取参数值，并转换为合适的Python类型
    确保返回合适的默认值而不是None
    """
    pattern = f'{param_name}=(.*?)(?:,|\))'
    match = re.search(pattern, text)
    if not match:
        return default
    
    value = match.group(1).strip()
    
    # 转换为Python对象
    if value == 'None':
        return default  # 如果值是None，返回默认值
    elif value == 'True':
        return True
    elif value == 'False':
        return False
    else:
        try:
            return ast.literal_eval(value)
        except:
            return value


def extract_string_param(text: str, param_name: str) -> Optional[str]:
    """特别处理字符串类型的参数，处理引号问题"""
    pattern = f'{param_name}=(.*?)(?:,|\))'
    match = re.search(pattern, text)
    if not match:
        return None
    
    value = match.group(1).strip()
    
    if value == 'None':
        return None
    
    # 如果是带引号的字符串，去掉外层引号
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    
    return value


def parse_model_outputs(outputs_text: str) -> List[Dict[str, Any]]:
    """解析模型输出文本并返回结构化的列表"""
    model_outputs = []
    
    # 从字典字符串中提取出所有的字典
    dict_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(dict_pattern, outputs_text)
    
    for match in matches:
        try:
            # 尝试将字符串转换为Python字典
            try:
                # 使用ast.literal_eval更安全地评估字符串表达式
                output_dict = ast.literal_eval(match)
                model_outputs.append(output_dict)
            except:
                # 如果直接转换失败，使用正则表达式提取关键信息
                action_keys = re.findall(r"'(\w+)':\s*\{", match)
                if action_keys:
                    action_key = action_keys[0]
                    # 简单解析参数
                    action_params = {}
                    params_match = re.search(r"'{}': (\{{.*?\}})".format(action_key), match, re.DOTALL)
                    if params_match:
                        param_text = params_match.group(1)
                        # 尝试解析参数
                        try:
                            action_params = ast.literal_eval(param_text)
                        except:
                            # 如果解析失败，使用更简单的方法
                            for param in re.findall(r"'(\w+)':\s*'?([\w\d\s:/._-]+)'?", param_text):
                                action_params[param[0]] = param[1]
                    
                    model_outputs.append({action_key: action_params, 'interacted_element': None})
        except Exception as e:
            # 对于无法解析的输出，记录但继续处理
            print(f"解析模型输出时出错: {e}")
            model_outputs.append({"raw_text": match, "error": str(e)})
    
    return model_outputs


# 使用示例
if __name__ == "__main__":
    input_file = "my_use/result.txt"
    output_dir = "my_use/result"
    convert_results_to_json(input_file, output_dir)