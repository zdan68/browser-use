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

# 创建日志目录
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# 创建统计报告目录
stats_dir = os.path.join(os.path.dirname(__file__), "stats")
os.makedirs(stats_dir, exist_ok=True)

# 配置日志系统
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
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
from tasks import TASK_SEQUENCE, get_task


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
            try:
                # 正确使用await等待协程完成
                result = await asyncio.wait_for(agent.run(), timeout=300)
                # 安全地记录结果类型而不是完整结果
                logger.info(f"任务{task}执行完成，结果类型: {type(result).__name__}")
                return result
            except asyncio.TimeoutError:
                logger.error(f"任务{task}执行超时")
                raise
        
        logger.info("-----------------------------------开始执行任务...")
        # Run the agent and get result
        result = loop.run_until_complete(run())
        logger.info("-----------------------------------任务执行完成")
        return result
    finally:
        # 添加资源清理代码
        async def cleanup():
            try:
                # 先保存身份验证状态（如果需要）
                if browser_context:
                    try:
                        # For each task create a unique state file name
                        state_file = os.path.join(os.path.dirname(__file__), f"auth_states/{task}_state.json")
                        os.makedirs(os.path.dirname(state_file), exist_ok=True)
                        
                        # Use session.context.cookies() method
                        if browser_context.session and browser_context.session.context:
                            cookies = await browser_context.session.context.cookies()
                            with open(state_file, 'w') as f:
                                json.dump(cookies, f)
                            logger.info(f"已保存身份验证状态（cookies）到 {state_file}")
                        else:
                            logger.warning(f"无法保存cookies，session或context为空")
                    except Exception as e:
                        logger.error(f"保存身份验证状态失败: {str(e)}")
                        
                    # 然后关闭上下文
                    logger.info("关闭浏览器上下文...")
                    await browser_context.close()
                
                # 保持浏览器实例活跃，不关闭它
                if browser:
                    logger.info("保持浏览器实例打开，以便后续使用...")
                    # 不调用 await browser.close()
            except Exception as e:
                logger.error(f"清理资源时出错: {str(e)}")
        
        if loop.is_running():
            # 如果循环还在运行，使用它来运行清理函数
            logger.info("使用当前事件循环清理资源...")
            loop.run_until_complete(cleanup())
        else:
            # 如果循环已经停止，重新启动它来运行清理函数
            logger.info("重新启动事件循环以清理资源...")
            loop.run_until_complete(cleanup())
        
        # 等待所有待处理任务完成，但排除当前任务
        current_task = asyncio.current_task(loop) if hasattr(asyncio, 'current_task') else None
        pending = [task for task in asyncio.all_tasks(loop) if task is not current_task]
        
        if pending:
            logger.info(f"等待 {len(pending)} 个待处理任务完成...")
            # 对于长时间没有完成的任务，先尝试等待一小段时间，然后取消它们
            try:
                # 等待最多3秒钟
                done, pending = loop.run_until_complete(asyncio.wait(pending, timeout=3, return_when=asyncio.ALL_COMPLETED))
                
                # 如果还有悬挂的任务，取消它们
                if pending:
                    logger.warning(f"有 {len(pending)} 个任务在3秒内未完成，正在取消...")
                    for task in pending:
                        task.cancel()
                    # 再等待一小段时间让取消操作生效
                    loop.run_until_complete(asyncio.wait(pending, timeout=1, return_when=asyncio.ALL_COMPLETED))
            except Exception as e:
                logger.error(f"取消待处理任务时出错: {e}")
        
        # 最后关闭事件循环
        logger.info("关闭事件循环...")
        loop.close()

def run_browser_tasks(tasks):
    """
    执行多个浏览器任务，最多同时运行3个任务。
    记录每个任务的耗时和重试次数，以及总体耗时数据。
    
    Args:
        tasks (list): 要执行的任务列表
    """
    # 使用信号量限制并发数量
    semaphore = threading.Semaphore(3)  # 固定为3，不再依赖任务数量
    
    # 如果任务列表为空，直接返回空统计信息
    if not tasks:
        logger.warning("任务列表为空，无需执行")
        return {"tasks": {}, "summary": {"total_tasks": 0, "successful_tasks": 0, "failed_tasks": 0}}
    
    # 记录整体开始时间
    overall_start_time = time.time()
    
    # 存储任务统计信息 - 简化为只包含关键数据
    stats = {
        "tasks": {},
        "summary": {}
    }
    
    stats_lock = threading.Lock()  # 防止多线程写入冲突
    
    def run_with_semaphore(task):
        task_info = get_task(task)
        task_name = task_info["name"]
        
        # 记录开始时间
        start_time = time.time()
        
        logger.info(f"开始任务: {task_name}")
        
        retries = 0
        success = False
        
        # 在函数的最外层添加 try-except，确保计算耗时和记录日志的代码一定会执行
        try:
            # 执行任务，最多重试3次
            while retries < 3:
                try:
                    with semaphore:
                        logger.info(f"获取信号量，准备执行任务: {task_name}")
                        # 记录结果类型而不是实际结果
                        result = run_single_task(task)
                        # 检查结果不是协程
                        if asyncio.iscoroutine(result):
                            logger.error(f"任务返回了一个未执行的协程：{result}")
                            raise RuntimeError("任务返回了未等待的协程")
                        logger.info(f"任务 {task_name} 成功执行，结果类型: {type(result).__name__}")
                        success = True
                    break
                except Exception as e:
                    retries += 1
                    logger.error(f"任务[{task_name}]执行失败 (尝试 {retries}/3): {str(e)}")
                    if retries < 3:
                        time.sleep(5)
                    else:
                        logger.error(f"任务[{task_name}]达到最大重试次数，放弃执行")
        except Exception as e:
            logger.error(f"任务[{task_name}]执行过程中发生严重错误: {str(e)}", exc_info=True)
        finally:
            # 一定会执行到这里，计算耗时并记录日志
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"完成任务: {task_name}, 耗时: {duration:.2f}秒, 重试: {retries}次, 成功: {success}")
            
        # 记录任务统计信息 - 不包含结果
        with stats_lock:
            stats["tasks"][str(task)] = {
                "name": task_name,
                "duration_seconds": duration,
                "duration_minutes": duration / 60,
                "retries": retries,
                "success": success,
                "start_time": datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S"),
            }
    
    # 创建并启动所有线程
    threads = []
    for task in tasks:
        thread = threading.Thread(target=run_with_semaphore, args=(task,))
        thread.start()
        threads.append(thread)
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 计算总体耗时
    overall_end_time = time.time()
    overall_duration = overall_end_time - overall_start_time
    
    # 统计成功和失败任务
    success_count = sum(1 for task_stat in stats["tasks"].values() if task_stat.get("success", False))
    
    # 更新总体统计信息
    stats["summary"] = {
        "total_tasks": len(tasks),
        "successful_tasks": success_count,
        "failed_tasks": len(tasks) - success_count,
        "total_duration_seconds": overall_duration,
        "total_duration_minutes": overall_duration / 60,
        "start_time": datetime.fromtimestamp(overall_start_time).strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": datetime.fromtimestamp(overall_end_time).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 输出简要统计信息
    logger.info(f"总任务数: {len(tasks)}")
    logger.info(f"成功任务: {success_count}")
    logger.info(f"失败任务: {len(tasks) - success_count}")
    logger.info(f"总耗时: {overall_duration:.2f}秒 ({overall_duration/60:.2f}分钟)")
    
    # 保存统计数据到JSON文件
    stats_file = os.path.join(stats_dir, f"stats_{current_time}.json")
    try:
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        logger.info(f"统计数据已保存到: {stats_file}")
    except Exception as e:
        logger.error(f"保存统计数据失败: {e}")
    
    return stats

def main():
    logger.info(f"开始执行任务，日志保存在: {log_file}")

    # 先执行3个登录任务，保留3个浏览器的实例
    # tasks = ["login", "login", "login"]
    tasks = ["login"]
    stats = run_browser_tasks(tasks)
    
    tasks = ["step1_understand"]
    
    # 执行任务并获取统计数据
    stats = run_browser_tasks(tasks)
    
    # 简单输出总结
    logger.info("所有任务执行完毕")

if __name__ == "__main__":
    main()
