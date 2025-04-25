import os

import browser_use.browser
import browser_use.browser.context
# Set environment variable to skip LLM API key verification - must be before other imports!
os.environ["SKIP_LLM_API_KEY_VERIFICATION"] = "1"

import threading
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
import asyncio

# Load environment variables from .env file before any other imports
load_dotenv()

# Now import browser_use after environment variables are set
print(f"当前工作目录: {os.getcwd()}")
import browser_use
print(f"browser_use.browser.context 包位置: {browser_use.browser.context.__file__}")
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig, BrowserContextWindowSize
from tasks import TASK_SEQUENCE, get_task


# Global configuration variables
headless = False
disable_security = True
window_w = 1680
window_h = 1100
save_recording_path = "./tmp/record_videos"
save_trace_path = "./tmp/traces"
cookies_file_path = "./cookies/cookies.json"
# 使用绝对路径
# auth_file_path = os.path.join(os.getcwd(), "my_use/cookies/auth.json")
# 或者相对于脚本所在位置的路径
auth_file_path = os.path.join(os.path.dirname(__file__), "cookies/auth.json")
chrome_cdp = ""

def create_llm() -> ChatOpenAI:
    """创建LLM实例"""
    
    return ChatOpenAI(
        model="deepseek-r1",
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
    
    try:
        # Initialize the LLM
        llm = create_llm()
        
        # Create browser instance with config
        browser_config = BrowserConfig(
            headless=headless,
            disable_security=disable_security,
            cdp_url=chrome_cdp,            
        )
        browser = Browser(config=browser_config)
        task_info = get_task(task)
        task_name = task_info["name"]
        print(f"Task: {task_name}")
        task_description = task_info["description"]        
        
        # Create browser context configuration
        context_config = BrowserContextConfig(
            trace_path=save_trace_path if save_trace_path else None,
            save_recording_path=save_recording_path if save_recording_path else None,
            no_viewport=False,
            browser_window_size=BrowserContextWindowSize(
                width=window_w, height=window_h
            ),
            cookies_file=cookies_file_path,
            auth_file=auth_file_path,
        )
        
        # Create browser context directly
        print("准备创建BrowserContext...")
        browser_context = BrowserContext(browser=browser, config=context_config)
        print("BrowserContext对象已创建，准备使用...")
        
        async def run():
            # Create an agent for this task
            agent = Agent(
                task=task_description, 
                llm=llm,
                browser=browser,
                browser_context=browser_context,
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
    stats_lock = threading.Lock()  # 防止多线程写入冲突
    
    def run_with_semaphore(task):
        import time
        import datetime
        
        task_info = get_task(task)
        task_name = task_info["name"]
        
        # 记录开始时间
        start_time = time.time()
        start_datetime = datetime.datetime.now()
        
        with stats_lock:
            task_stats[task] = {
                "name": task_name,
                "start_time": start_time,
                "start_datetime": start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            }
            
        print(f"开始任务: {task_name}")
        print(f"开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            with semaphore:
                result = run_single_task(task)
        finally:
            # 记录结束时间
            end_time = time.time()
            end_datetime = datetime.datetime.now()
            duration_seconds = end_time - start_time
            duration_minutes = duration_seconds / 60
            
            with stats_lock:
                task_stats[task].update({
                    "end_time": end_time,
                    "end_datetime": end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": duration_seconds,
                    "duration_minutes": duration_minutes,
                })
            
            print(f"完成任务: {task_name}")
            print(f"结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"耗时: {duration_seconds:.2f}秒 ({duration_minutes:.2f}分钟)")
            print("-" * 50)
            
            return result
    
    # 创建所有线程
    threads = []
    for task in tasks:
        thread = threading.Thread(target=run_with_semaphore, args=(task,))
        threads.append(thread)
    
    # 启动所有线程 - 信号量会确保最多同时有3个线程执行run_single_task
    for thread in threads:
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 打印所有任务的统计信息
    print("\n" + "=" * 80)
    print("任务执行统计报告")
    print("=" * 80)
    print(f"{'任务名称':<30} {'开始时间':<20} {'结束时间':<20} {'耗时(秒)':<10} {'耗时(分钟)':<10}")
    print("-" * 80)
    
    for task_id, stats in task_stats.items():
        print(f"{stats['name']:<30} {stats['start_datetime']:<20} {stats['end_datetime']:<20} {stats['duration_seconds']:.2f}秒 {stats['duration_minutes']:.2f}分钟")
    
    # 计算总耗时
    total_duration = max([stats['end_time'] for stats in task_stats.values()]) - min([stats['start_time'] for stats in task_stats.values()])
    print("-" * 80)
    print(f"总耗时: {total_duration:.2f}秒 ({total_duration/60:.2f}分钟)")
    print("=" * 80)
    
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
