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


def convert_results_to_json(input_file: str, output_dir: str,task_id: int = 0) -> None:
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

    if task_id == 0:
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
    else:
        # 保存为JSON
        output_file = os.path.join(output_dir, f"task_{task_id}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)

        print(f"结构化结果已保存到: {output_file}") 

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
        
        # 使用更可靠的方法找到所有ActionResult对象的范围
        action_result_starts = [m.start() for m in re.finditer(r'ActionResult\(', actions_text)]
        num_action_results = len(action_result_starts)
        
        for i in range(num_action_results):
            start_pos = action_result_starts[i]
            # 确定ActionResult对象的结束位置（匹配的括号）
            end_pos = find_matching_parenthesis(actions_text, start_pos)
            
            if end_pos == -1:  # 没有找到匹配的括号
                if i < num_action_results - 1:
                    end_pos = action_result_starts[i+1]  # 使用下一个ActionResult的开始位置
                else:
                    end_pos = len(actions_text)  # 使用文本结束
            
            action_result_text = actions_text[start_pos:end_pos]
            
            # 提取参数值
            is_done = extract_param_safe(action_result_text, 'is_done', default=False)
            success = extract_param_safe(action_result_text, 'success')
            error = extract_param_safe(action_result_text, 'error')
            include_in_memory = extract_param_safe(action_result_text, 'include_in_memory', default=False)
            
            # 直接提取完整的extracted_content，不做任何截断或转换
            extracted_content = extract_full_content(action_result_text, 'extracted_content')
            
            action_result = ActionResult(
                is_done=is_done,
                success=success,
                extracted_content=extracted_content,
                error=error,
                include_in_memory=include_in_memory if include_in_memory is not None else False
            )
            
            action_results.append(action_result)
        
        # 解析model_outputs
        model_outputs = parse_model_outputs(model_outputs_text)
        
        # 创建一个自定义的AgentHistoryList
        custom_agent_history = CustomAgentHistoryList(action_results, model_outputs)
        agent_history_lists.append(custom_agent_history)
    
    return agent_history_lists


def find_matching_parenthesis(text: str, open_pos: int) -> int:
    """
    查找匹配的括号位置
    
    Args:
        text: 要搜索的文本
        open_pos: 开括号的位置
        
    Returns:
        匹配的闭括号位置，如果没有找到则返回-1
    """
    if open_pos >= len(text) or text[open_pos] != 'A':  # ActionResult的第一个字符
        return -1
    
    # 确保我们找到了ActionResult(的位置
    actual_open = text.find('(', open_pos)
    if actual_open == -1:
        return -1
    
    # 计数器记录括号嵌套
    count = 1
    pos = actual_open + 1
    
    while pos < len(text) and count > 0:
        if text[pos] == '(':
            count += 1
        elif text[pos] == ')':
            count -= 1
            if count == 0:
                return pos + 1  # 返回闭括号后的位置
        pos += 1
    
    return -1  # 没有找到匹配的括号


def extract_param_safe(text: str, param_name: str, default: Any = None) -> Any:
    """安全提取参数值"""
    param_pos = text.find(f'{param_name}=')
    if param_pos == -1:
        return default
    
    # 获取参数值的开始位置
    value_start = param_pos + len(f'{param_name}=')
    
    # 检查是否为None
    if text[value_start:].startswith('None'):
        return None
    
    # 检查是否为布尔值
    if text[value_start:].startswith('True'):
        return True
    if text[value_start:].startswith('False'):
        return False
    
    # 查找下一个逗号或闭括号，确定值的结束位置
    comma_pos = text.find(',', value_start)
    paren_pos = text.find(')', value_start)
    
    # 确定哪一个标记最先出现
    if comma_pos == -1:
        end_pos = paren_pos
    elif paren_pos == -1:
        end_pos = comma_pos
    else:
        end_pos = min(comma_pos, paren_pos)
    
    if end_pos == -1:  # 如果都没找到
        value = text[value_start:].strip()
    else:
        value = text[value_start:end_pos].strip()
    
    # 处理引号
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        value = value[1:-1]
    
    try:
        return ast.literal_eval(value)
    except:
        return value


def extract_full_content(text: str, param_name: str) -> Optional[str]:
    """
    专用于提取完整的字符串内容，特别是extracted_content
    不会截断或修改内容
    
    Args:
        text: ActionResult的完整文本
        param_name: 参数名称
        
    Returns:
        完整的参数内容，如果不存在则返回None
    """
    param_start = text.find(f'{param_name}=')
    if param_start == -1:
        return None
    
    content_start = param_start + len(f'{param_name}=')
    remaining = text[content_start:]
    
    # 处理None值
    if remaining.startswith('None'):
        return None
    
    # 查找内容的起始引号和类型
    if not (remaining.startswith("'") or remaining.startswith('"')):
        return None  # 不是字符串
    
    quote_char = remaining[0]
    content_start += 1  # 跳过起始引号
    
    # 从这个位置开始查找匹配的引号
    pos = content_start
    in_content = True
    content = ""
    
    while pos < len(text) and in_content:
        char = text[pos]
        
        # 检查是否为结束引号
        if char == quote_char:
            # 检查前面是否有奇数个反斜杠（转义）
            backslash_count = 0
            i = pos - 1
            while i >= 0 and text[i] == '\\':
                backslash_count += 1
                i -= 1
            
            # 如果反斜杠数为偶数，则这是一个真正的结束引号
            if backslash_count % 2 == 0:
                # 找到了匹配的引号
                content = text[content_start:pos]
                in_content = False
        
        pos += 1
    
    return content


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
    input_file = "my_use/results/20250427_150245/result_4.txt"
    output_dir = "my_use/results/20250427_150245"
    convert_results_to_json(input_file, output_dir,5)