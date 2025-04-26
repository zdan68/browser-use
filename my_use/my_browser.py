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
import time
import datetime

# 创建日志目录
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# 创建统计报告目录
stats_dir = os.path.join(os.path.dirname(__file__), "stats")
os.makedirs(stats_dir, exist_ok=True)

# 配置日志系统
current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"browser_tasks_{current_time}.log")

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
from my_use.tasks import TASK_SEQUENCE, get_task


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

def run_single_task(task):
    """
    Execute a single browser task in a separate thread
    
    Args:
        task (str): The task to be performed by the agent
    """
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    browser = None
    browser_context = None
    
    try:
        # Initialize the LLM
        llm = create_llm()
    
        # Create browser instance with config
        browser_config = BrowserConfig(
            headless=headless,
            disable_security=disable_security,
        )
        browser = Browser(config=browser_config)
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
            wait_for_network_idle_page_load_time=1.0
        )
        
        # Create browser context directly
        logger.info("准备创建BrowserContext...")
        browser_context = BrowserContext(browser=browser, config=context_config)
        logger.info("BrowserContext对象已创建，准备使用...")
        
        async def run():
            # Create an agent for this task
            agent = Agent(
                task=task_description, 
                llm=llm,
                browser=browser,
                browser_context=browser_context,
                enable_memory=False,  # 禁用内存系统，避免连接错误
            )
            
            # Run the agent and get result
            return await agent.run()
        
        # Run the agent and get result
        result = loop.run_until_complete(run())
        
        # Print result directly from this thread
        print(f"Task: {task}")
        print(f"Result: {result}")
        print("-" * 50)
        
        return result
    finally:
        # Clean up the event loop
        loop.close()

def run_browser_tasks(tasks):
    """
    Execute multiple browser tasks with a maximum of 3 concurrent tasks.
    Records the start time, end time, and duration of each task.
    
    Args:
        tasks (list): List of tasks to be performed by the agents
    """
    # 使用信号量限制并发数量为3
    semaphore = threading.Semaphore(3)
    
    # 存储任务统计信息
    task_stats = {}
    
    def run_with_semaphore(task):

        task_info = get_task(task)
        task_name = task_info["name"]
        
        # 记录开始时间
        start_time = time.time()
        start_datetime = datetime.datetime.now()

        result = {
            "name": task_name,
            "start_time": start_time,
            "start_datetime": start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": None,
            "end_datetime": None,
            "duration_seconds": None,
            "duration_minutes": None,
            "task_result": None,
                }
            
        print(f"开始任务: {task_name}")
        print(f"开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            with semaphore:
                result["task_result"] = run_single_task(task)
        finally:
            # 记录结束时间
            end_time = time.time()
            end_datetime = datetime.datetime.now()
            result["end_time"] = end_time
            result["end_datetime"] = end_datetime.strftime('%Y-%m-%d %H:%M:%S')
            result["duration_seconds"] = end_time - start_time
            result["duration_minutes"] = result["duration_seconds"] / 60
            
        return result
    
    # 创建所有线程
    threads = []
    thread_to_task = {}  # 用于跟踪每个线程对应的任务
    results = []
    for task in tasks:
        thread = threading.Thread(target=lambda t=task: results.append(run_with_semaphore(t)))
        thread_to_task[thread] = task
        threads.append(thread)        
    
    # 启动所有线程 - 信号量会确保最多同时有3个线程执行run_single_task
    for thread in threads:
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()

    # 结果写入文件
    with open(os.path.join(stats_dir, f"browser_tasks_{current_time}.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
       
    print("All tasks completed!")

def main():
    # Example task - modify this according to your needs
    # task1 = "Go to weather.com and check the weather forecast for San Francisco"
    # task2 = "Go to google.com and search for 'browser use'"
    # task3 = "Go to amazon.com and search for 'laptop'"
    # tasks = [task1, task2, task3]

    tasks = TASK_SEQUENCE
    
    # Run tasks in parallel using threads
    run_browser_tasks(tasks)

if __name__ == "__main__":
    main()
