import os
import logging
from datetime import datetime
import sys
import json

import browser_use.browser
import browser_use.browser.context
# Set environment variable to skip LLM API key verification - must be before other imports!
os.environ["SKIP_LLM_API_KEY_VERIFICATION"] = "1"

import threading
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
import asyncio

import datetime
import time

# 将browser_task的函数直接内联到代码中
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

# 任务顺序
TASK_SEQUENCE = [
    "login",
    "baidu",
    "zhihu",
    "google",
    "step1_understand",
    "step2_analyze_passage",
    "step3_analyze_context",
    "step4_judge_reason",
    "step5_make_choice"
]

# 获取任务信息
def get_task(task_key):
    """获取任务信息"""
    from pathlib import Path
    # 获取任务文件夹路径
    tasks_dir = Path(__file__).parent / "tasks"
    task_file = tasks_dir / f"{task_key}.md"
    
    try:
        with open(task_file, 'r', encoding='utf-8') as f:
            description = f.read()
    except FileNotFoundError:
        description = f"任务文件 {task_key}.md 不存在"
    
    name = TASK_NAMES.get(task_key, "未知任务")
    return {
        "name": name,
        "description": description
    }

# 创建日志目录
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# 配置日志系统
current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"browser_tasks_{current_time}.log")

# 创建统计报告目录
stats_dir = os.path.join(os.path.dirname(__file__), "stats")
os.makedirs(stats_dir, exist_ok=True)
# 创建stats_dir中的任务专用目录
os.makedirs(os.path.join(stats_dir, f"browser_tasks_{current_time}"), exist_ok=True)

# 创建logger对象
logger = logging.getLogger("browser_tasks")
logger.setLevel(logging.INFO)  # 将默认级别改为INFO，减少DEBUG日志

# 创建文件处理器，将日志写入文件
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 创建控制台处理器，在控制台显示日志
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Load environment variables from .env file before any other imports
load_dotenv()

# Now import browser_use after environment variables are set
logger.info(f"当前工作目录: {os.getcwd()}")
import browser_use
logger.info(f"browser_use.browser.context 包位置: {browser_use.browser.context.__file__}")
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig, BrowserContextWindowSize

# 使用sys.path添加当前目录并导入tasks
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Global configuration variables
headless = False
disable_security = True
window_w = 1440
window_h = 990
save_recording_path = None
save_history_path = "./tmp/history"
save_trace_path = None
# cookies_file_path = "./cookies/cookies.json"
# 使用绝对路径
# auth_file_path = os.path.join(os.getcwd(), "my_use/cookies/auth.json")
# 或者相对于脚本所在位置的路径
auth_file_path = os.path.join(os.path.dirname(__file__), "cookies/auth.json")

def create_llm() -> ChatOpenAI:
    """创建LLM实例"""
    
    return ChatOpenAI(
        model="qwen2.5-coder-32b-instruct",
        temperature=0.3,
        streaming=True,
        base_url=os.getenv("DASH_SCOPE_BASE_URL"),
    )

def run_single_task(task, shared_browser):
    """
    Execute a single browser task
    
    Args:
        task (str): The task to be performed by the agent
        shared_browser (Browser): 共享的Browser实例
    """
    try:
        # Initialize the LLM
        llm = create_llm()
    
        task_info = get_task(task)
        task_name = task_info["name"]
        logger.info(f"执行任务: {task_name}")
        task_description = task_info["description"]        
        
        # Create browser context configuration
        context_config = BrowserContextConfig(
            trace_path=save_trace_path if save_trace_path else None,
            save_recording_path=save_recording_path if save_recording_path else None,
            no_viewport=False,
            browser_window_size=BrowserContextWindowSize(
                width=window_w, height=window_h
            ),
            wait_for_network_idle_page_load_time=1.0,
        )
        
        # Create browser context directly - using the shared browser
        logger.info(f"为任务 {task_name} 创建BrowserContext...")
        browser_context = BrowserContext(browser=shared_browser, config=context_config)
        logger.info(f"任务 {task_name} 的BrowserContext对象已创建，准备使用...")
        
        # 创建一个简单的异步函数来运行任务
        async def run_task():
            # Create an agent for this task
            agent = Agent(
                task=task_description, 
                llm=llm,
                browser=shared_browser,  # 使用共享的Browser实例
                browser_context=browser_context,  # 每个任务使用独立的上下文
                enable_memory=False,  # 禁用内存系统，避免连接错误
            )
            logger.info(f"任务 {task_name} 的Agent对象已创建，准备使用...")
            # 运行agent并获取结果
            result = await agent.run()
            logger.info(f"任务 {task_name} 的Agent执行完毕")
            return result
            
        # 使用asyncio.run直接执行异步任务
        logger.info(f"任务 {task_name} 运行中")
        # 在当前线程中获取或创建一个事件循环
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果当前线程没有事件循环，创建一个新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        result = loop.run_until_complete(run_task())
        logger.info(f"任务 {task_name} 运行结束")
        
        return result
    except Exception as e:
        logger.error(f"任务 {task_name} 执行出错: {str(e)}")
        return {"error": str(e), "status": "failed"}

def run_browser_tasks(tasks):
    """
    Execute multiple browser tasks with a maximum of 3 concurrent tasks.
    Records the start time, end time, and duration of each task.
    
    Args:
        tasks (list): List of tasks to be performed by the agents
    """
    # 使用信号量限制并发数量为3
    semaphore = threading.Semaphore(3)
    
    # 创建一个共享的Browser实例
    browser_config = BrowserConfig(
        headless=headless,
        disable_security=disable_security,
    )
    
    logger.info("创建共享浏览器实例...")
    shared_browser = Browser(config=browser_config)
    logger.info("共享浏览器实例创建成功")
    
    def run_with_semaphore(task):
        task_info = get_task(task)
        task_name = task_info["name"]
        
        # 记录开始时间
        start_datetime = datetime.datetime.now()

        result = {
            "name": task_name,
            "start_time": start_datetime,
            "start_datetime": start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": None,
            "end_datetime": None,
            "duration_seconds": None,
            "duration_minutes": None,
            "task_result": None,
            "status": "pending"
        }
            
        logger.info(f"任务 {task_name} 开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            with semaphore:
                logger.info(f"任务 {task_name} 开始运行run_single_task")
                
                try:
                    task_result = run_single_task(task, shared_browser)
                    logger.info(f"任务 {task_name} 执行结果: {task_result}")
                    result["task_result"] = task_result
                    
                    # 检查任务执行结果
                    if isinstance(task_result, dict) and task_result.get("error"):
                        result["status"] = "error"
                        result["error"] = task_result.get("error")
                        logger.error(f"任务 {task_name} 执行失败: {task_result.get('error')}")
                    else:
                        result["status"] = "success"
                        logger.info(f"任务 {task_name} 执行成功")
                
                except Exception as e:
                    error_msg = f"任务 {task_name} 执行过程中发生异常: {str(e)}"
                    logger.error(error_msg)
                    result["status"] = "error"
                    result["error"] = str(e)
                    
                logger.info(f"任务 {task_name} run_single_task 结束, 状态: {result['status']}")
        finally:
            # 记录结束时间
            end_datetime = datetime.datetime.now()
            result["end_datetime"] = end_datetime.strftime('%Y-%m-%d %H:%M:%S')
            result["duration_seconds"] = (end_datetime - start_datetime).seconds
            result["duration_minutes"] = result["duration_seconds"] / 60
            logger.info(f"任务 {task_name} 结束, 状态: {result['status']}, 耗时: {result['duration_seconds']}秒")

        # result 存到文件
        try:
            task_result_dir = os.path.join(stats_dir, f"browser_tasks_{current_time}")
            os.makedirs(task_result_dir, exist_ok=True)
            result_file = os.path.join(task_result_dir, f"{task_name}.json")
            
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"任务 {task_name} 结果已保存到: {result_file}")
        except Exception as e:
            logger.error(f"保存任务 {task_name} 结果时出错: {e}")    

        return result
    
    start_datetime = datetime.datetime.now()
    logger.info(f"任务列表： {tasks}，开始运行，开始时间：{start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    # 创建所有线程
    threads = []
    results = []
    # 如果包含login,先运行
    if "login" in tasks:
        logger.info(f"先执行登录任务...")
        results.append(run_with_semaphore("login"))
        tasks.remove("login")
        logger.info(f"登录任务已完成，开始执行其他任务：{tasks}")
    
    for task in tasks:
        logger.info(f"为任务 {task} 创建线程...")
        thread = threading.Thread(target=lambda t=task: results.append(run_with_semaphore(t)), name=f"Thread-{task}")
        threads.append(thread)        
    
    # 启动所有线程 - 信号量会确保最多同时有3个线程执行run_single_task
    for thread in threads:
        logger.info(f"启动线程 {thread.name}...")
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        logger.info(f"等待线程 {thread.name} 完成...")
        thread.join()
        logger.info(f"线程 {thread.name} 已完成")
    
    # 计算总耗时
    end_datetime = datetime.datetime.now()
    total_duration = end_datetime - start_datetime
    logger.info(f"任务列表： {tasks}，结束运行,结束时间：{end_datetime.strftime('%Y-%m-%d %H:%M:%S')},总耗时：{total_duration.seconds}秒,{total_duration.seconds/60}分钟")
    results.append({
        "start_datetime": start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
        "end_datetime": end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
        "total_duration_seconds": total_duration.seconds,
        "total_duration_minutes": total_duration.seconds/60
    })

    # 结果写入文件
    try:
        with open(os.path.join(stats_dir, f"browser_tasks_{current_time}.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存到: {os.path.join(stats_dir, f'browser_tasks_{current_time}.json')}")
    except Exception as e:
        logger.error(f"保存结果时出错: {e}")
       
    # 最后关闭共享浏览器
    try:
        logger.info("所有任务完成，关闭共享浏览器...")
        # 使用事件循环来关闭浏览器
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(shared_browser.close())
        logger.info("共享浏览器已关闭")
    except Exception as e:
        logger.error(f"关闭共享浏览器时出错: {e}")
    
    print("All tasks completed!")

def main():
    # 定义要运行的任务
    tasks = ["login", "baidu", "zhihu", "google"]  # 只包含需要运行的任务
    
    logger.info("====== 开始运行主函数 ======")
    logger.info(f"将要执行的任务: {tasks}")
    
    # Run tasks in parallel using threads with a shared browser
    run_browser_tasks(tasks)
    
    logger.info("====== 主函数执行完毕 ======")

if __name__ == "__main__":
    logger.info("====== 脚本开始执行 ======")
    main()
    logger.info("====== 脚本执行完毕 ======")
