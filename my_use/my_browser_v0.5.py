import asyncio
from browser_use import Agent, Controller
from langchain_openai import ChatOpenAI
import os
import logging
from dotenv import load_dotenv
from browser_use.browser.browser import Browser, BrowserConfig, BrowserContextConfig
import time
from datetime import datetime
import json
from concurrent.futures import ThreadPoolExecutor
import threading
from my_use.tasks import read_task_description, get_task, get_common_instructions

start_timestamp = time.time()
start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
# 结果文件目录
result_dir = "my_use/results/"+start_time
os.makedirs(result_dir, exist_ok=True)
# 创建日志目录
log_dir = "my_use/logs/"+start_time
os.makedirs(log_dir, exist_ok=True)

# 加载环境变量
load_dotenv()

# 创建全局共享的控制器实例
shared_controller = Controller()

# 创建全局共享的LLM实例
shared_llm = ChatOpenAI(
    model="qwen-plus",
    temperature=0.3,
    streaming=True,
    base_url=os.getenv("DASH_SCOPE_BASE_URL"),
)

# 创建全局日志记录器
logger = None

# 配置日志系统
def setup_logger():   
    # 创建logger对象
    logger = logging.getLogger("browser_agent")
    logger.setLevel(logging.DEBUG)
    
    # 创建日志文件名（添加时间戳）
    log_file = os.path.join(log_dir, f"browser_run_{start_time}.log")
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 导入任务定义模块
from my_use.tasks import TASK_SEQUENCE, get_task, get_common_instructions
from my_use.convert_results import convert_results_to_json

# 添加运行任务的函数
def run_agent(task_id, task_description, task_name):
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')}] 任务 {task_id} 开始执行")
    # 创建日志目录
    logs_dir = f"{log_dir}/agent_{task_id}"
    os.makedirs(logs_dir, exist_ok=True)
    
    task_start_time = time.time()
    print(f"开始执行任务 {task_id}: {task_name}")
    
    # 异步运行代码
    async def run_async():
        # 使用全局共享的controller和llm
        global shared_controller, shared_llm
        
        # 创建Agent
        agent = Agent(
            task=task_description,
            llm=shared_llm,  # 使用共享LLM
            controller=shared_controller,  # 使用共享controller
            save_conversation_path=logs_dir,
            enable_memory=False
        )
        
        try:
            # 运行agent
            result = await agent.run(max_steps=20)
            
            # 保存结果
            try:
                current_page = await agent.browser_context.get_current_page()
                result_path = os.path.join(result_dir, f"agent_{task_id}.txt")
                with open(result_path, "w", encoding="utf-8") as f:
                    f.write(await current_page.content())
            except Exception as save_error:
                print(f"无法保存任务 {task_id} 的结果: {save_error}")
                
            print(f"任务 {task_id} 成功完成")
            return result
            
        except Exception as e:
            error_path = os.path.join(log_dir, f"agent_{task_id}_error.txt")
            with open(error_path, "w", encoding="utf-8") as f:
                f.write(f"任务 {task_id} 执行错误: {str(e)}")
            print(f"任务 {task_id} 失败: {e}")
            raise e
        finally:
            # 关闭浏览器上下文，但不关闭controller
            try:
                await agent.browser_context.close()
            except:
                pass
    
    # 执行异步代码
    try:
        result = asyncio.run(run_async())
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')}] 任务 {task_id} 执行完成")
        
        # 计算任务执行时间
        task_end_time = time.time()
        task_duration = task_end_time - task_start_time
        task_duration_minutes = round(task_duration / 60, 2)
        
        print(f"任务 {task_id} ({task_name}) 执行时长: {task_duration:.2f}秒 ({task_duration_minutes}分钟)")
        
        # 保存单个任务的结果和时间统计
        task_result = {
            "task_id": task_id,
            "task_name": task_name,
            "start_time": datetime.fromtimestamp(task_start_time).strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": datetime.fromtimestamp(task_end_time).strftime('%Y-%m-%d %H:%M:%S'),
            "duration_seconds": task_duration,
            "duration_minutes": task_duration_minutes,
            "status": "completed",
            # "result": str(result)[:500] + "..." if len(str(result)) > 500 else str(result)  # 只保存部分结果避免文件过大
        }
        
        # 保存任务结果到JSON文件
        task_result_file = os.path.join(result_dir, f"task_result_{task_id}.json")
        with open(task_result_file, "w", encoding="utf-8") as f:
            json.dump(task_result, f, ensure_ascii=False, indent=2)


        # 保存原始结果到txt文件
        result_file = os.path.join(result_dir, f"result_{task_id}.txt")
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(str(result))

        # 使用convert_results_to_json函数将结果转换为JSON格式
        convert_results_to_json(result_file, result_dir,task_id)
        
        return result, task_duration
    except Exception as e:
        task_end_time = time.time()
        task_duration = task_end_time - task_start_time
        
        # 记录失败任务的结果
        task_result = {
            "task_id": task_id,
            "task_name": task_name,
            "start_time": datetime.fromtimestamp(task_start_time).strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": datetime.fromtimestamp(task_end_time).strftime('%Y-%m-%d %H:%M:%S'),
            "duration_seconds": task_duration,
            "duration_minutes": round(task_duration / 60, 2),
            "status": "failed",
            "error": str(e)
        }
        
        # 保存失败任务结果到JSON文件
        task_result_file = os.path.join(result_dir, f"task_result_{task_id}.json")
        with open(task_result_file, "w", encoding="utf-8") as f:
            json.dump(task_result, f, ensure_ascii=False, indent=2)
        
        raise e

def process_question(question_id, tasks):
    """
    处理一个问题的所有任务，使用多线程并行执行
    
    Args:
        question_id: 问题ID
        tasks: 该问题的所有任务列表
    """
    global logger
    logger = setup_logger()
    
    logger.info(f"开始处理问题 {question_id} 的任务序列，共 {len(tasks)} 个任务")
    
    all_results = []
    task_durations = []
    
    # 使用线程池并行执行任务序列中的所有任务
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        # 提交所有任务到线程池
        futures = [
            executor.submit(run_agent, task["id"], task["description"], TASK_SEQUENCE[task["id"]-1]) 
            for task in tasks
        ]
        
        # 等待所有任务完成并收集结果
        completed = 0
        for i, future in enumerate(futures):
            try:
                result, duration = future.result()
                all_results.append(result)
                task_durations.append(duration)
                completed += 1
                logger.info(f"问题 {question_id} 进度: {completed}/{len(tasks)}")
            except Exception as e:
                logger.error(f"问题 {question_id} 的任务执行失败: {e}")
                all_results.append(None)
                task_durations.append(0)
    
    logger.info(f"问题 {question_id} 的所有任务执行完毕")
    
    # 输出每个任务的执行时间
    for i, duration in enumerate(task_durations):
        if duration > 0:
            duration_minutes = round(duration / 60, 2)
            logger.info(f"任务 {i+1} ({TASK_SEQUENCE[i]}) 执行时长: {duration:.2f}秒 ({duration_minutes}分钟)")
    
    # 计算时间统计
    non_zero_durations = [d for d in task_durations if d > 0]
    avg_duration = sum(non_zero_durations) / len(non_zero_durations) if non_zero_durations else 0
    min_duration = min(non_zero_durations) if non_zero_durations else 0
    max_duration = max(non_zero_durations) if non_zero_durations else 0
    
    logger.info(f"任务时间统计 - 平均: {avg_duration:.2f}秒, 最短: {min_duration:.2f}秒, 最长: {max_duration:.2f}秒")
    
    # 1. 先将原始结果保存为txt文件
    result_file = os.path.join(result_dir, "result.txt")
    logger.info(f"保存原始结果到: {result_file}")
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(str(all_results))
    
    # 2. 使用convert_results_to_json函数将结果转换为JSON格式
    try:
        logger.info("开始将结果转换为JSON格式...")
        convert_results_to_json(result_file, result_dir)
        logger.info(f"结果已成功转换为JSON格式并保存到: {result_dir}")
    except Exception as e:
        logger.error(f"转换为JSON时出错: {e}", exc_info=True)
    
    # 保存整体时间统计文件
    end_timestamp = time.time()
    duration = end_timestamp - start_timestamp
    duration_minutes = round(duration / 60, 2)
    
    task_result = {
        "tasks": TASK_SEQUENCE,
        "start_time": datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S'),   
        "end_time": datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
        "duration_minutes": f"{duration_minutes}分钟",
        "task_durations": [
            {
                "task_id": i+1,
                "task_name": TASK_SEQUENCE[i],
                "duration_seconds": duration,
                "duration_minutes": round(duration / 60, 2)
            } 
            for i, duration in enumerate(task_durations)
        ],
        "time_stats": {
            "average_seconds": avg_duration,
            "min_seconds": min_duration,
            "max_seconds": max_duration
        }
    }
    task_result_file = os.path.join(result_dir, "task_result.json")
    with open(task_result_file, "w", encoding="utf-8") as f:
        json.dump(task_result, f, ensure_ascii=False, indent=2)
    
    return all_results, task_durations

if __name__ == "__main__":
    print("启动任务执行系统...")
    print(f"使用全局共享Controller和LLM进行多任务并行处理")
    start_time = time.time()
    
    # 为TASK_SEQUENCE创建任务列表
    tasks = [
        {"id": i+1, "description": read_task_description(task_name) + get_common_instructions()} 
        for i, task_name in enumerate(TASK_SEQUENCE)
    ]
    
    print(f"共加载了 {len(tasks)} 个任务")
    
    # 直接在主进程中处理所有任务
    all_results, task_durations = process_question("main_question", tasks)
    
    end_time = time.time()
    total_duration = end_time - start_time
    print(f"任务处理完成，总耗时: {total_duration:.2f} 秒，{total_duration / 60:.2f} 分钟，任务数: {len(tasks)}")