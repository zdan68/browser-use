#!/usr/bin/env python3

import json
import sys
import os
import requests
import argparse
from typing import Dict, Any

# OpenAI API configuration - you'll need to provide your API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_uc_prompt(question_id: str, json_config: Dict[str, Any]) -> str:
    """Create the prompt for the LLM based on the UC create template"""
    prompt = """# 角色: 自动化浏览器测试脚本生成专家

您是一位专门为自动化浏览器测试工具（如 "Browser Use"）创建详细操作指令的专家。您的任务是根据提供的 `questionId` 和一个描述在线学习活动步骤的 JSON 配置文件 (`jsonConfig`)，生成一个包含一系列测试任务详情的 JSON 对象。

# 输入:

1.  **`questionId`**: {question_id}
2.  **`jsonConfig`**: 
{json_config}

# 任务:

根据输入的 `questionId` 和 `jsonConfig`，生成一个 **单一的 JSON 对象** 作为最终输出。该 JSON 对象需包含一个名为 `tasks` 的列表。`tasks` 列表中的每个元素都代表 `jsonConfig.steps` 数组中的一个步骤，并详细描述了如何测试该步骤。

# 对 `tasks` 列表中每个任务对象的要求:

每个任务对象必须包含以下四个键：

1.  **`task_id`** (String): 任务的唯一标识符，直接使用对应 JSON 步骤的 `id` 值。
2.  **`task_name`** (String): 任务的人类可读名称，直接使用对应 JSON 步骤的 `title` 值。
3.  **`task_description`** (String): 对该测试任务目标的简短中文描述。例如："测试引导步骤 ①：理解任务 - 插入段落的选择操作与反馈验证。"
4.  **`task_prompt_markdown`** (String): 一个 **完整的 Markdown 格式的文本字符串**。这个字符串是为当前任务生成的详细测试提示，必须满足以下所有要求：
    *   **语言与人设:** 必须使用 **简体中文** 编写，并采用 **六年级学生"毛毛"** 的第一人称视角和口吻。
    *   **Markdown 结构:** 遵循详细结构，包括任务标识标题、角色定义、任务目标、初始导航与登录（含测试 URL 和登录备用流程）、定位步骤、确认位置、执行步骤（阅读、**核心操作**、获取建议）、检查反馈（含 **3 次尝试限制** 和问题记录）。
    *   **核心操作推断:**
        *   对于 `radio` 字段，根据 `validation` 确定正确选项的 `label`，并在 Markdown 中明确指示选择该项。
        *   对于 `textarea` 字段，根据 `placeholder` 或 `description` 生成合适的示例输入，并在 Markdown 中明确指示输入内容和位置。
    *   **通用指示融入:** 将关键点（滚动查找、等待加载、仔细阅读、记录问题）自然融入 Markdown 文本中。
    *   **正确性:** Markdown 中指示的操作必须反映 JSON 配置中定义的 **正确答案或预期输入**。
    *   **测试 URL:** Markdown 中的测试网址必须正确嵌入提供的 `questionId`：``https://47.251.82.88/courses/20082/chat/0/null?questionId={question_id}&test=true``

# 输出格式要求:

*   最终输出 **必须** 是一个 **单一的、格式良好的 JSON 对象**。
*   该 JSON 对象必须包含一个名为 `tasks` 的键，其值为一个 **JSON 数组**。
*   数组中的每个元素都是一个 **JSON 对象**，包含 `task_id`, `task_name`, `task_description`, 和 `task_prompt_markdown` 四个键，其值符合上述要求。
"""
    return prompt.format(
        question_id=question_id,
        json_config=json.dumps(json_config, ensure_ascii=False, indent=2)
    )

def call_openai_api(prompt: str) -> str:
    """Call OpenAI API to get the generated UC task"""
    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable.")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    data = {
        "model": "gpt-4o-mini", # Use appropriate model
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that generates browser automation test scripts."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2  # Lower temperature for more consistent output
    }
    
    response = requests.post(
        os.environ.get("DASH_SCOPE_BASE_URL", "https://api.openai.com/v1/chat/completions"),
        headers=headers,
        json=data
    )
    
    if response.status_code != 200:
        raise Exception(f"API call failed with status code {response.status_code}: {response.text}")
    
    return response.json()["choices"][0]["message"]["content"]

def extract_json_from_response(response: str) -> Dict[str, Any]:
    """Extract and parse JSON from the LLM response"""
    # Try to extract JSON if the response contains other text
    try:
        # First attempt: Try to parse the entire response as JSON
        return json.loads(response)
    except json.JSONDecodeError:
        # Second attempt: Look for JSON within the response
        try:
            # Look for JSON object between curly braces
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # If no JSON structure found, raise error
                raise ValueError("No JSON structure found in the response")
        except (json.JSONDecodeError, ValueError):
            # If still failing, raise an error
            raise ValueError("Failed to extract valid JSON from the LLM response")

def main():
    parser = argparse.ArgumentParser(description="Generate UC tasks using LLM")
    parser.add_argument("--question_id", required=True, help="Question ID for the task")
    parser.add_argument("--config_file", required=True, help="Path to the JSON configuration file")
    parser.add_argument("--output_file", required=True, help="Path for the output file")
    
    args = parser.parse_args()
    
    # Load the JSON configuration
    json_config = load_json_file(args.config_file)
    
    # Create the prompt
    prompt = create_uc_prompt(args.question_id, json_config)
    
    # Call the LLM API
    try:
        response = call_openai_api(prompt)
        
        # Extract and parse the JSON from the response
        tasks_json = extract_json_from_response(response)
        
        # Write the result to the output file
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(tasks_json, f, ensure_ascii=False, indent=2)
        
        print(f"Successfully generated UC tasks and saved to {args.output_file}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 