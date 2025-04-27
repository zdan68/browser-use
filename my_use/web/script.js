// API 基础URL
const API_BASE_URL = '/api';
let currentData = null;
let currentTaskId = null;
let actionModal = null;

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化模态框
    actionModal = new bootstrap.Modal(document.getElementById('actionModal'));
    
    // 加载结果列表
    loadResultsList();
    
    // 添加选择器事件监听
    document.getElementById('resultSelect').addEventListener('change', function() {
        loadResultData(this.value);
    });
});

// 加载可用结果列表
async function loadResultsList() {
    try {
        const response = await fetch(`${API_BASE_URL}/results`);
        if (!response.ok) throw new Error('Failed to fetch results list');
        
        const data = await response.json();
        const selectElement = document.getElementById('resultSelect');
        
        // 清空现有选项
        selectElement.innerHTML = '';
        
        // 添加新选项
        if (data.results && data.results.length > 0) {
            data.results.forEach(result => {
                const option = document.createElement('option');
                option.value = result.path;
                option.textContent = result.date;
                selectElement.appendChild(option);
            });
            
            // 自动加载第一个结果
            loadResultData(data.results[0].path);
        } else {
            selectElement.innerHTML = '<option value="">无可用结果</option>';
            showError('未找到任何结果数据');
        }
    } catch (error) {
        console.error('加载结果列表失败:', error);
        showError(`加载结果列表失败: ${error.message}`);
    }
}

// 加载指定结果数据
async function loadResultData(resultPath) {
    try {
        // 显示加载状态
        document.getElementById('summary-container').innerHTML = '<div class="loading">加载中...</div>';
        document.getElementById('task-list').innerHTML = '';
        document.getElementById('task-details').innerHTML = '<div class="loading">加载中...</div>';
        document.getElementById('action-history-card').style.display = 'none';
        
        const response = await fetch(`${API_BASE_URL}/results/${resultPath}`);
        if (!response.ok) throw new Error('Failed to fetch result data');
        
        const data = await response.json();
        currentData = data;
        
        // 显示摘要信息
        renderSummary(data.summary);
        
        // 显示任务列表
        renderTaskList(data.tasks);
        
        // 默认选中第一个任务
        if (data.tasks && data.tasks.length > 0) {
            selectTask(data.tasks[0].id);
        }
    } catch (error) {
        console.error('加载结果数据失败:', error);
        showError(`加载结果数据失败: ${error.message}`);
    }
}

// 渲染摘要信息
function renderSummary(summary) {
    const container = document.getElementById('summary-container');
    
    // 基本摘要信息
    let html = `
        <dl>
            <dt>总任务数</dt>
            <dd>${summary.total_tasks}</dd>
            
            <dt>成功任务数</dt>
            <dd>${summary.successful_tasks} <span class="badge bg-success">${Math.round(summary.successful_tasks / summary.total_tasks * 100)}%</span></dd>
            
            <dt>失败任务数</dt>
            <dd>${summary.failed_tasks} <span class="badge bg-danger">${Math.round(summary.failed_tasks / summary.total_tasks * 100)}%</span></dd>
            
            <dt>总操作数</dt>
            <dd>${summary.total_actions}</dd>
            
            <dt>错误数</dt>
            <dd>${summary.total_errors}</dd>
        </dl>
    `;
    
    // 如果有任务元数据信息，添加到摘要中
    if (currentData.task_meta && Object.keys(currentData.task_meta).length > 0) {
        const meta = currentData.task_meta;
        
        html += `
            <hr>
            <h6 class="text-primary">任务执行信息</h6>
            <dl>
                ${meta.tasks ? `
                <dt>执行的任务</dt>
                <dd>${meta.tasks.join(', ')}</dd>
                ` : ''}
                
                ${meta.start_time ? `
                <dt>开始时间</dt>
                <dd>${meta.start_time}</dd>
                ` : ''}
                
                ${meta.end_time ? `
                <dt>结束时间</dt>
                <dd>${meta.end_time}</dd>
                ` : ''}
                
                ${meta.duration_minutes ? `
                <dt>执行时长</dt>
                <dd>${meta.duration_minutes} 分钟</dd>
                ` : ''}
            </dl>
        `;
        
        // 如果有任务时长信息，添加任务时长表格
        if (meta.task_durations && meta.task_durations.length > 0) {
            html += `
                <h6 class="text-primary mt-3">任务时长统计</h6>
                <div class="table-responsive">
                    <table class="table table-sm table-striped">
                        <thead>
                            <tr>
                                <th>任务 ID</th>
                                <th>任务名称</th>
                                <th>执行时长 (分钟)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${meta.task_durations.map(duration => `
                                <tr>
                                    <td>${duration.task_id}</td>
                                    <td>${duration.task_name}</td>
                                    <td>${duration.duration_minutes.toFixed(2)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                        ${meta.time_stats ? `
                        <tfoot>
                            <tr>
                                <td colspan="2" class="text-end"><strong>平均时长:</strong></td>
                                <td>${(meta.time_stats.average_seconds / 60).toFixed(2)}</td>
                            </tr>
                            <tr>
                                <td colspan="2" class="text-end"><strong>最短时长:</strong></td>
                                <td>${(meta.time_stats.min_seconds / 60).toFixed(2)}</td>
                            </tr>
                            <tr>
                                <td colspan="2" class="text-end"><strong>最长时长:</strong></td>
                                <td>${(meta.time_stats.max_seconds / 60).toFixed(2)}</td>
                            </tr>
                        </tfoot>
                        ` : ''}
                    </table>
                </div>
            `;
        }
    }
    
    container.innerHTML = html;
}

// 渲染任务列表
function renderTaskList(tasks) {
    const container = document.getElementById('task-list');
    
    // 清空现有内容
    container.innerHTML = '';
    
    // 添加任务项
    tasks.forEach(task => {
        // 获取任务时长信息（从task_meta中）
        let durationInfo = '';
        if (currentData.task_meta && currentData.task_meta.task_durations) {
            const taskDuration = currentData.task_meta.task_durations.find(d => d.task_id === task.id);
            if (taskDuration && taskDuration.duration_minutes !== undefined) {
                durationInfo = `<span class="task-duration-badge">${taskDuration.duration_minutes.toFixed(1)}分钟</span>`;
            }
        }
        
        const listItem = document.createElement('li');
        listItem.className = 'task-item';
        listItem.dataset.taskId = task.id;
        listItem.innerHTML = `
            <div class="d-flex align-items-center">
                <span class="badge ${task.success ? 'bg-success' : 'bg-danger'} rounded-pill me-1">${task.id}</span>
                <span class="task-name">${task.name}</span>
                ${durationInfo}
            </div>
        `;
        
        // 添加点击事件
        listItem.addEventListener('click', function() {
            selectTask(task.id);
        });
        
        container.appendChild(listItem);
    });
}

// 选择任务
function selectTask(taskId) {
    currentTaskId = taskId;
    
    // 更新任务列表选中状态
    const taskItems = document.querySelectorAll('.task-item');
    taskItems.forEach(item => {
        if (parseInt(item.dataset.taskId) === taskId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    // 获取任务数据
    const task = currentData.tasks.find(t => t.id === taskId);
    if (!task) return;
    
    // 更新任务详情
    renderTaskDetails(task);
    
    // 显示操作历史
    renderActionHistory(task);
    document.getElementById('action-history-card').style.display = 'block';
}

// 渲染任务详情
function renderTaskDetails(task) {
    const container = document.getElementById('task-details');
    const titleElement = document.getElementById('task-title');
    
    // 获取任务时长信息（从task_meta中）
    let durationInfo = '未知';
    if (currentData.task_meta && currentData.task_meta.task_durations) {
        const taskDuration = currentData.task_meta.task_durations.find(d => d.task_id === task.id);
        if (taskDuration && taskDuration.duration_minutes !== undefined) {
            durationInfo = `${taskDuration.duration_minutes.toFixed(2)} 分钟`;
        }
    }
    
    // 更新标题
    titleElement.textContent = `${task.name} ${task.success ? '✅' : '❌'}`;
    
    // 生成详情HTML
    let html = `
        <div class="row">
            <div class="col-md-6">
                <h3 class="h6 fw-bold">基本信息</h3>
                <ul class="list-group mb-3">
                    <li class="list-group-item d-flex justify-content-between">
                        <span>状态</span>
                        <span class="${task.success ? 'status-success' : 'status-error'}">
                            ${task.success ? '成功' : '失败'}
                        </span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>执行时长</span>
                        <span class="badge bg-info">${durationInfo}</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>总操作数</span>
                        <span>${task.total_actions}</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>错误数</span>
                        <span>${task.errors.length}</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>完成状态</span>
                        <span>${task.is_done ? '已完成' : '未完成'}</span>
                    </li>
                </ul>
            </div>
            
            <div class="col-md-6">
                <h3 class="h6 fw-bold">访问的URL</h3>
                <ul class="list-group url-list mb-3">
                    ${task.urls_visited.map(url => `<li class="list-group-item">${url}</li>`).join('')}
                </ul>
            </div>
        </div>
        
        <div class="row">
            <div class="col-12">
                <h3 class="h6 fw-bold">完成消息</h3>
                <div class="alert alert-secondary">
                    ${task.completion_message || '无完成信息'}
                </div>
            </div>
        </div>
    `;
    
    // 如果有错误，显示错误信息
    if (task.errors.length > 0) {
        html += `
            <div class="row">
                <div class="col-12">
                    <h3 class="h6 fw-bold">错误信息</h3>
                    <div class="alert alert-danger">
                        <ul class="mb-0">
                            ${task.errors.map(err => `<li>${err.error || '未知错误'}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

// 渲染操作历史
function renderActionHistory(task) {
    const container = document.getElementById('action-history');
    
    // 清空现有内容
    container.innerHTML = '';
    
    // 添加操作项
    task.all_results.forEach((action, index) => {
        const row = document.createElement('tr');
        row.className = 'action-row';
        
        // 确定操作状态类和图标
        let statusClass = '';
        let statusIcon = '';
        
        if (action.is_done) {
            statusClass = action.success ? 'status-success' : 'status-error';
            statusIcon = action.success ? '✅' : '❌';
        } else if (action.error) {
            statusClass = 'status-error';
            statusIcon = '❌';
        } else {
            statusClass = 'status-pending';
            statusIcon = '⏳';
        }
        
        // 获取匹配的模型输出
        const modelOutput = task.all_model_outputs[index] || {};
        const actionType = Object.keys(modelOutput).filter(key => key !== 'interacted_element')[0] || 'unknown';
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${actionType || '未知'}</td>
            <td>${action.extracted_content ? truncateText(action.extracted_content, 50) : (action.error || '')}</td>
            <td class="${statusClass}">${statusIcon}</td>
        `;
        
        // 添加点击事件，显示详细信息
        row.addEventListener('click', function() {
            showActionDetails(action, modelOutput, index + 1);
        });
        
        container.appendChild(row);
    });
}

// 显示操作详情
function showActionDetails(action, modelOutput, actionNumber) {
    const modalBody = document.getElementById('actionModalBody');
    const modalTitle = document.getElementById('actionModalLabel');
    
    modalTitle.textContent = `操作 #${actionNumber} 详情`;
    
    // 获取操作类型
    const actionType = Object.keys(modelOutput).filter(key => key !== 'interacted_element')[0] || 'unknown';
    
    // 构建详情HTML
    let html = `
        <h5>操作类型: ${actionType}</h5>
        
        <div class="mt-3">
            <h6>输入参数:</h6>
            <pre class="bg-light p-2 rounded">${syntaxHighlight(JSON.stringify(modelOutput[actionType] || {}, null, 2))}</pre>
        </div>
        
        <div class="mt-3">
            <h6>执行结果:</h6>
            <div class="table-responsive">
                <table class="table table-bordered">
                    <tbody>
                        <tr>
                            <th>已完成</th>
                            <td>${action.is_done ? '是' : '否'}</td>
                        </tr>
                        ${action.success !== null ? `
                        <tr>
                            <th>成功</th>
                            <td>${action.success ? '是' : '否'}</td>
                        </tr>` : ''}
                        ${action.extracted_content ? `
                        <tr>
                            <th>提取内容</th>
                            <td>${action.extracted_content}</td>
                        </tr>` : ''}
                        ${action.error ? `
                        <tr>
                            <th>错误</th>
                            <td class="text-danger">${action.error}</td>
                        </tr>` : ''}
                    </tbody>
                </table>
            </div>
        </div>
        
        ${modelOutput.interacted_element ? `
        <div class="mt-3">
            <h6>交互元素:</h6>
            <pre class="bg-light p-2 rounded">${syntaxHighlight(JSON.stringify(modelOutput.interacted_element, null, 2))}</pre>
        </div>` : ''}
    `;
    
    modalBody.innerHTML = html;
    actionModal.show();
}

// 显示错误消息
function showError(message) {
    document.getElementById('summary-container').innerHTML = `
        <div class="alert alert-danger">${message}</div>
    `;
    
    document.getElementById('task-list').innerHTML = '';
    document.getElementById('task-details').innerHTML = `
        <div class="alert alert-danger">${message}</div>
    `;
    
    document.getElementById('action-history-card').style.display = 'none';
}

// 文本截断
function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// JSON语法高亮
function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
        let cls = 'json-number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'json-key';
            } else {
                cls = 'json-string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'json-boolean';
        } else if (/null/.test(match)) {
            cls = 'json-null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
} 