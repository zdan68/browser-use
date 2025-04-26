import asyncio
from browser_use import Agent, Controller
from langchain_openai import ChatOpenAI
import os
import sys
from dotenv import load_dotenv
from browser_use.browser.browser import Browser, BrowserConfig, BrowserContextConfig
import time
import json


# 加载环境变量
load_dotenv()

# 导入任务定义模块
from my_use.tasks import TASK_SEQUENCE, get_task
from my_use.convert_results import convert_results_to_json

async def main():
    async def auth_hook(agent):
        page = await agent.browser_context.get_current_page()
        try:
            # Add wait options and timeout
            await page.goto(
                'http://47.251.82.88/courses/20082/chat/0/31?questionId=24494&test=true',
                wait_until='networkidle',
                timeout=30000
            )
            # Set token after page loads
            await page.evaluate("""
                localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6InNsX3Rlc3QiLCJpYXQiOjE3NDU1NzE5NzQsImV4cCI6MTc0ODE2Mzk3NH0.1jfhjvl-zNNqOMvOm1NTuADzpyU0CZRF9xLRbEaFKtI');
                localStorage.setItem('user', JSON.stringify({"id":31,"username":"sl_test","password":"e10adc3949ba59abbe56e057f20f883e","nickname":"sl_test","phoneNumber":null,"model":"2","parentId":"28"}));
                localStorage.setItem('user_setting', 'null');
            """)
        except Exception as e:
            print(f"Navigation error: {e}")    

    start_time = time.time()
    print(f"开始时间: {start_time}")
    controller = Controller()
    
    # Configure browser to stay visible
    browser_config = BrowserConfig(
        headless=False,
        disable_security=True,
        extra_browser_args=["--disable-web-security"],  # 添加这行以解决localStorage安全问题
    )

    browser_context_config = BrowserContextConfig()   

    # Create reusable browser instance
    browser = Browser(config=browser_config)    
    # context = await browser.new_context(config=browser_context_config)
       
    llm = ChatOpenAI(
        model="qwen-plus",
        temperature=0.3,
        streaming=True,
        base_url=os.getenv("DASH_SCOPE_BASE_URL"),
    )

    agent_tasks = []
    for task_key in TASK_SEQUENCE:
        # 获取任务描述
        task_info = get_task(task_key)
        task_description = task_info["description"]
        agent = Agent(
            task=task_description,  # 使用实际任务描述而不是键名
            llm=llm,
            controller=controller,
            # browser_context=context
            enable_memory=False  # 禁用内存功能
        )
        agent_tasks.append(agent.run())
    
    # Run agents concurrently
    results = await asyncio.gather(*agent_tasks)
    
    end_time = time.time()
    print(f"结束时间: {end_time}")
    print(f"总时间: {end_time - start_time}秒, 分钟: {round((end_time - start_time) / 60, 2)}分钟")    
    # 将结果保存到文件
    result_dir = "my_use/result"
    os.makedirs(result_dir, exist_ok=True)
    
    # 1. 先将原始结果保存为txt文件
    result_file = os.path.join(result_dir, "result.txt")
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(str(results))
    print(f"原始结果已保存到: {result_file}")
    
    # 2. 使用convert_results_to_json函数将结果转换为JSON格式
    try:
        convert_results_to_json(result_file, result_dir)
        print(f"结果已成功转换为JSON格式并保存到: {result_dir}")
    except Exception as e:
        print(f"转换为JSON时出错: {e}")

if __name__ == "__main__":
    asyncio.run(main())