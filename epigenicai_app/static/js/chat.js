// 聊天应用主逻辑
class ChatApp {
    constructor() {
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.taskPanel = document.getElementById('taskPanel');
        this.taskList = document.getElementById('taskList');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        
        this.currentTaskId = null;
        this.taskCheckInterval = null;
        
        this.initEventListeners();
    }
    
    initEventListeners() {
        // 发送按钮点击
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // 输入框回车发送
        this.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // 自动调整输入框高度
        this.chatInput.addEventListener('input', () => {
            this.chatInput.style.height = 'auto';
            this.chatInput.style.height = this.chatInput.scrollHeight + 'px';
        });
    }
    
    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message) return;
        
        // 清空输入框
        this.chatInput.value = '';
        this.chatInput.style.height = 'auto';
        
        // 移除欢迎消息
        const welcomeMsg = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMsg) {
            welcomeMsg.remove();
        }
        
        // 添加用户消息
        this.addMessage(message, 'user');
        
        // 添加处理中消息（而不是弹窗）
        const processingMsg = this.addMessage('正在分析您的请求，请稍候...', 'assistant');
        processingMsg.classList.add('processing-message');
        
        try {
            // 添加调试信息
            console.log('发送消息:', message);
            
            // 发送消息到后端
            const response = await fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({ message })
            });
            
            console.log('响应状态:', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('响应数据:', data);
            
            if (data.status === 'success') {
                // 移除处理中消息
                const processingMsg = document.querySelector('.processing-message');
                if (processingMsg) {
                    processingMsg.remove();
                }
                
                // 显示助手回复
                this.addMessage(data.response, 'assistant');
                
                // 如果有任务ID，开始监控任务进度
                if (data.task_id) {
                    this.currentTaskId = data.task_id;
                    this.startTaskMonitoring();
                }
            } else {
                throw new Error(data.message || '请求失败');
            }
        } catch (error) {
            console.error('请求错误:', error);
            
            // 移除处理中消息
            const processingMsg = document.querySelector('.processing-message');
            if (processingMsg) {
                processingMsg.remove();
            }
            
            this.addMessage('抱歉，处理您的请求时出现错误：' + error.message, 'assistant');
        }
    }
    
    addMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = sender === 'user' ? 
            '<i class="fas fa-user"></i>' : 
            '<i class="fas fa-robot"></i>';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // 如果是助手消息，支持Markdown渲染
        if (sender === 'assistant') {
            contentDiv.innerHTML = this.renderMarkdown(content);
        } else {
            contentDiv.textContent = content;
        }
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        this.chatMessages.appendChild(messageDiv);
        
        // 滚动到底部
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        
        return messageDiv;
    }
    
    renderMarkdown(text) {
        // 简单的Markdown渲染
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="report-link">$1</a>')
            .replace(/\n/g, '<br>');
    }
    
    startTaskMonitoring() {
        // 显示任务面板
        this.taskPanel.style.display = 'flex';
        
        // 清空之前的任务列表
        this.taskList.innerHTML = '';
        
        // 开始定期检查任务状态
        this.checkTaskStatus();
        this.taskCheckInterval = setInterval(() => {
            this.checkTaskStatus();
        }, 2000); // 每2秒检查一次
    }
    
    async checkTaskStatus() {
        try {
            const response = await fetch(`/api/task-status/${this.currentTaskId}/`);
            const data = await response.json();
            
            if (data.status === 'success') {
                this.updateTaskList(data.tasks);
                
                // 如果所有任务完成，停止监控
                if (data.completed) {
                    clearInterval(this.taskCheckInterval);
                    this.showCompletionMessage(data);
                }
            }
        } catch (error) {
            console.error('检查任务状态失败:', error);
        }
    }
    
    updateTaskList(tasks) {
        this.taskList.innerHTML = '';
        
        tasks.forEach(task => {
            const taskItem = document.createElement('div');
            taskItem.className = `task-item ${task.status}`;
            
            taskItem.innerHTML = `
                <div class="task-header">
                    <span class="task-name">${task.name}</span>
                    <span class="task-status">${this.getStatusText(task.status)}</span>
                </div>
                ${task.progress !== undefined ? `
                    <div class="task-progress">
                        <div class="progress-bar" style="width: ${task.progress}%"></div>
                    </div>
                ` : ''}
            `;
            
            this.taskList.appendChild(taskItem);
        });
    }
    
    getStatusText(status) {
        const statusMap = {
            'pending': '等待中',
            'running': '进行中',
            'completed': '已完成',
            'failed': '失败'
        };
        return statusMap[status] || status;
    }
    
    showCompletionMessage(data) {
        // 显示完成消息和报告内容
        if (data.summary && data.summary.trim()) {
            // 直接显示报告内容
            this.addMessage('分析已完成！以下是您的研究报告：', 'assistant');
            setTimeout(() => {
                this.addMessage(data.summary, 'assistant');
            }, 500);
        } else if (data.report_url) {
            // 如果没有摘要，提供链接
            this.addMessage('分析已完成！正在生成报告...', 'assistant');
            setTimeout(() => {
                const reportMessage = `
                    报告已生成完成！
                    
                    [查看完整报告](${data.report_url})
                    
                    **点击上方链接查看详细分析报告**
                `;
                this.addMessage(reportMessage, 'assistant');
            }, 1000);
        } else {
            this.addMessage('分析已完成！', 'assistant');
        }
    }
    
    showLoading() {
        this.loadingOverlay.style.display = 'flex';
    }
    
    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }
    
    getCookie(name) {
        // 优先使用window中的token
        if (name === 'csrftoken' && window.csrfToken) {
            return window.csrfToken;
        }
        
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    new ChatApp();
});

// 任务面板切换
function toggleTaskPanel() {
    const taskPanel = document.getElementById('taskPanel');
    if (taskPanel.style.display === 'none') {
        taskPanel.style.display = 'flex';
    } else {
        taskPanel.style.display = 'none';
    }
}