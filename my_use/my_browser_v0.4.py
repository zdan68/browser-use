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

start_timestamp = time.time()
start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
# 结果文件目录
result_dir = "my_use/results/"+start_time
os.makedirs(result_dir, exist_ok=True)
# 创建日志目录
log_dir = "my_use/logs/"+start_time
os.makedirs(log_dir, exist_ok=True)

# 配置日志系统
def setup_logger():   
    # 创建logger对象
    logger = logging.getLogger("browser_agent")
    logger.setLevel(logging.INFO)
    
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

# 加载环境变量
load_dotenv()

# 导入任务定义模块
from my_use.tasks import TASK_SEQUENCE, get_task
from my_use.convert_results import convert_results_to_json

async def main():
    # 设置日志系统
    logger = setup_logger()
    
    async def auth_hook(agent):
        page = await agent.browser_context.get_current_page()
        try:
            # Add wait options and timeout
            logger.info("导航到认证页面...")
            await page.goto(
                'http://47.251.82.88/login',
                wait_until='networkidle',
                timeout=30000
            )
            # Set token after page loads
            logger.info("设置本地存储认证信息...")
            await page.evaluate("""
                localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6InNsX3Rlc3QiLCJpYXQiOjE3NDU1NzE5NzQsImV4cCI6MTc0ODE2Mzk3NH0.1jfhjvl-zNNqOMvOm1NTuADzpyU0CZRF9xLRbEaFKtI');
                localStorage.setItem('user', JSON.stringify({"id":31,"username":"sl_test","password":"e10adc3949ba59abbe56e057f20f883e","nickname":"sl_test","phoneNumber":null,"model":"2","parentId":"28"}));
                localStorage.setItem('user_setting', 'null');
            """)
        except Exception as e:
            logger.error(f"导航错误: {e}")    

    logger.info(f"任务开始执行，开始时间: {start_time}")
    
    logger.info("初始化控制器...")
    controller = Controller()
    
    # Configure browser to stay visible
    logger.info("配置浏览器...")
    browser_config = BrowserConfig(
        headless=False,
        disable_security=True,
        extra_browser_args=["--disable-web-security"],  # 添加这行以解决localStorage安全问题
    )

    browser_context_config = BrowserContextConfig()   

    # Create reusable browser instance
    logger.info("创建浏览器实例...")
    browser = Browser(config=browser_config)    
    # context = await browser.new_context(config=browser_context_config)
       
    logger.info("初始化语言模型...")
    llm = ChatOpenAI(
        model="qwen-plus",
        temperature=0.3,
        streaming=True,
        base_url=os.getenv("DASH_SCOPE_BASE_URL"),
    )

    agent_tasks = []
    logger.info(f"准备执行任务序列: {TASK_SEQUENCE}")
    for task_key in TASK_SEQUENCE:
        # 获取任务描述
        task_info = get_task(task_key)
        task_description = task_info["description"]
        logger.info(f"创建任务: {task_key} - {task_description[:50]}...")
        agent = Agent(
            task=task_description,  # 使用实际任务描述而不是键名
            llm=llm,
            controller=controller,
            # browser_context=context
            enable_memory=False  # 禁用内存功能
        )
        agent_tasks.append(agent.run())
    
    # Run agents concurrently
    logger.info(f"开始并行执行 {len(agent_tasks)} 个任务...")
    results = await asyncio.gather(*agent_tasks)
    logger.info(f"执行完毕 {len(agent_tasks)} 个任务...")

    end_timestamp = time.time()
    duration = end_timestamp - start_timestamp
    duration_minutes = round(duration / 60, 2)
    logger.info(f"任务执行完成，结束时间: {datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"总执行时间: {duration:.2f}秒 ({duration_minutes}分钟)")

    # 1. 先将原始结果保存为txt文件
    result_file = os.path.join(result_dir, "result.txt")
    logger.info(f"保存原始结果到: {result_file}")
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(str(results))
    
    # 2. 使用convert_results_to_json函数将结果转换为JSON格式
    try:
        logger.info("开始将结果转换为JSON格式...")
        convert_results_to_json(result_file, result_dir)
        logger.info(f"结果已成功转换为JSON格式并保存到: {result_dir}")
    except Exception as e:
        logger.error(f"转换为JSON时出错: {e}", exc_info=True)

    # 保存时间统计文件
    task_result = {
        "tasks" : TASK_SEQUENCE,
        "start_time": datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S'),   
        "end_time": datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
        "duration_minutes": f"{duration_minutes}分钟"
    }
    task_result_file = os.path.join(result_dir, "task_result.json")
    with open(task_result_file, "w", encoding="utf-8") as f:
        json.dump(task_result, f, ensure_ascii=False)        
        
    logger.info("任务完全结束")

if __name__ == "__main__":
    asyncio.run(main())