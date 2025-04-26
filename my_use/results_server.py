import os
import json
import logging
from flask import Flask, jsonify, send_from_directory, current_app, abort
from flask_cors import CORS
import argparse

# 配置命令行参数解析器
parser = argparse.ArgumentParser(description='启动结果展示服务器')
parser.add_argument('--port', type=int, default=8000, help='服务器端口号 (默认: 8000)')
args = parser.parse_args()

# 创建日志目录
os.makedirs('my_use/logs', exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('my_use/logs/results_server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('results_server')

# 确保静态目录存在
static_dir = os.path.join(os.path.dirname(__file__), 'web')
os.makedirs(static_dir, exist_ok=True)

app = Flask(__name__, static_folder=static_dir)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # 明确配置CORS

# 结果数据目录
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

@app.route('/api/results')
def get_results_list():
    """获取所有可用的结果列表"""
    try:
        logger.info(f"扫描结果目录: {RESULTS_DIR}")
        results = []
        
        # 查找所有日期文件夹
        for item in os.listdir(RESULTS_DIR):
            item_path = os.path.join(RESULTS_DIR, item)
            if os.path.isdir(item_path):
                json_file = os.path.join(item_path, 'structured_results.json')
                if os.path.exists(json_file):
                    results.append({
                        'path': item,
                        'date': item
                    })
        
        # 按日期排序（最新的在前）
        results.sort(key=lambda x: x['date'], reverse=True)
        
        logger.info(f"发现 {len(results)} 个结果文件: {results}")
        return jsonify({'results': results})
    except Exception as e:
        logger.error(f"获取结果列表出错: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/results/<path:result_path>')
def get_result_data(result_path):
    """获取指定结果的数据"""
    try:
        # 构建完整文件路径
        if os.path.isdir(os.path.join(RESULTS_DIR, result_path)):
            # 如果是目录，添加文件名
            results_file = os.path.join(RESULTS_DIR, result_path, 'structured_results.json')
            task_meta_file = os.path.join(RESULTS_DIR, result_path, 'task_result.json')
        else:
            # 否则直接使用路径
            results_file = os.path.join(RESULTS_DIR, result_path)
            # 尝试在同一目录查找task_result.json
            task_meta_file = os.path.join(os.path.dirname(results_file), 'task_result.json')
            
        logger.info(f"尝试读取结果文件: {results_file}")
        logger.info(f"尝试读取任务元数据文件: {task_meta_file}")
        
        # 检查结果文件是否存在
        if not os.path.exists(results_file):
            logger.error(f"结果文件不存在: {results_file}")
            return jsonify({'error': 'Result file not found'}), 404
        
        # 读取结果JSON文件
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 尝试读取任务元数据文件（如果存在）
            task_meta = {}
            if os.path.exists(task_meta_file):
                try:
                    with open(task_meta_file, 'r', encoding='utf-8') as f:
                        task_meta = json.load(f)
                    logger.info(f"成功读取任务元数据文件: {task_meta_file}")
                except Exception as e:
                    logger.warning(f"读取任务元数据文件失败: {e}")
            
            # 将任务元数据添加到结果数据中
            data['task_meta'] = task_meta
            
            logger.info(f"成功读取结果文件: {results_file}")
            return jsonify(data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            return jsonify({'error': f'Invalid JSON: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"获取结果数据出错: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/')
def serve_index():
    """提供前端页面"""
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except Exception as e:
        logger.error(f"提供索引页面出错: {e}", exc_info=True)
        return f"错误: {str(e)}", 500

@app.route('/<path:path>')
def serve_static(path):
    """提供静态文件"""
    try:
        return send_from_directory(app.static_folder, path)
    except Exception as e:
        logger.error(f"提供静态文件出错 ({path}): {e}", exc_info=True)
        return f"错误: 文件 {path} 不存在", 404

if __name__ == '__main__':
    port = args.port
    logger.info(f"结果展示服务器启动中，使用端口: {port}...")
    logger.info(f"静态文件目录: {app.static_folder}")
    logger.info(f"结果数据目录: {RESULTS_DIR}")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=True)
    except OSError as e:
        logger.error(f"启动服务器失败: {e}")
        logger.info(f"尝试使用端口 {port+1}...")
        try:
            app.run(host='0.0.0.0', port=port+1, debug=True)
        except OSError:
            logger.info("尝试使用随机端口...")
            app.run(host='0.0.0.0', port=0, debug=True) 