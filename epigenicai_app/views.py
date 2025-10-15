# epigenicai_app/views.py
import json
import uuid
import asyncio
import threading
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# AIagent相关视图
def AIagent_view(request):
    """AI助手主页面视图"""
    if request.method == 'GET':
        return render(request, 'AIagent.html')
    else:
        return HttpResponse("Method not allowed", status=405)

def AIagent_chat(request):
    """处理AI对话请求的API视图"""
    import json
    from django.http import JsonResponse


    if request.method == 'POST':
        try:
            # 解析请求数据
            data = json.loads(request.body)
            message = data.get('message', '').strip()

            if not message:
                return JsonResponse({
                    'status': 'error',
                    'message': '消息不能为空'
                }, status=400)
                        # 打印当前历史（调试用）

            # 获取会话上下文
            context = {
                'history': request.session.get('chat_history', []),
                'user_id': request.session.session_key
            }

            try:
                # 初始化Agent
                from agent_core.agents.control_agent import ControlAgent
                agent = ControlAgent()

                # process方法直接返回字符串！
                response_text = agent.process(message, context)  # ← 这里直接就是字符串

            except Exception as e:
                print(f"Agent处理错误: {str(e)}")
                # 使用备用响应
                response_text = get_fallback_response(message)

            # 更新会话历史
            if 'chat_history' not in request.session:
                request.session['chat_history'] = []

            request.session['chat_history'].append({
                'user': message,
                'assistant': response_text
            })

            # 限制历史记录长度
            if len(request.session['chat_history']) > 10:
                request.session['chat_history'] = request.session['chat_history'][-10:]

            request.session.modified = True

            return JsonResponse({
                'status': 'success',
                'response': response_text  # 直接使用字符串
            })

        except Exception as e:
            print(f"处理请求时出错: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': '服务器内部错误'
            }, status=500)

    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)