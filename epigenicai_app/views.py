# epigenicai_app/views.py
import json
import asyncio
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

# 全局Agent实例（避免重复创建）
_control_agent = None

def get_control_agent():
    """获取Control Agent单例"""
    global _control_agent
    if _control_agent is None:
        from agent_core.agents.control_agent import ControlAgent
        _control_agent = ControlAgent()
    return _control_agent


def AIagent_view(request):
    """AI助手主页面视图"""
    if request.method == 'GET':
        return render(request, 'AIagent.html')
    else:
        return HttpResponse("Method not allowed", status=405)


def AIagent_chat(request):
    """处理AI对话请求的API视图 - 支持多轮对话"""
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

            # 获取或创建session_id
            if not request.session.session_key:
                request.session.create()
            session_id = request.session.session_key

            # 准备上下文（包含Django session中的信息）
            context = {
                'user_ip': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'django_session_data': dict(request.session),
            }

            try:
                # 获取Agent实例
                agent = get_control_agent()

                # 使用异步运行器来调用异步方法
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # 调用异步的process_message方法，传递上下文
                    result = loop.run_until_complete(
                        agent.process_message(message, session_id, context)
                    )
                finally:
                    loop.close()

                # 从返回的字典中提取信息
                response_text = result.get('message', '抱歉，无法处理您的请求')
                
                # 构建完整的响应
                response_data = {
                    'status': 'success',
                    'response': response_text,
                    'session_id': session_id  # 返回session_id供前端参考
                }
                
                # 添加额外信息
                if result.get('genes'):
                    response_data['genes'] = result['genes']
                
                if result.get('confidence'):
                    response_data['confidence'] = result['confidence']
                
                if result.get('state'):
                    response_data['analysis_state'] = result['state']
                
                if result.get('task_started'):
                    response_data['task_started'] = True
                
                # 获取对话历史数量（用于前端显示）
                conversation_history = agent.get_conversation_history(session_id)
                response_data['conversation_count'] = len(conversation_history)

            except ImportError as e:
                print(f"导入Agent错误: {str(e)}")
                response_text = "AI助手模块未正确配置，请联系管理员"
                response_data = {
                    'status': 'error',
                    'response': response_text
                }
                
            except Exception as e:
                print(f"Agent处理错误: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # 使用备用响应
                response_text = get_fallback_response(message)
                response_data = {
                    'status': 'success',
                    'response': response_text
                }

            return JsonResponse(response_data)

        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '无效的JSON数据'
            }, status=400)
            
        except Exception as e:
            print(f"处理请求时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return JsonResponse({
                'status': 'error',
                'message': '服务器内部错误',
                'details': str(e)
            }, status=500)

    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)


def AIagent_history(request):
    """获取对话历史API"""
    if request.method == 'GET':
        try:
            # 获取session_id
            session_id = request.session.session_key
            if not session_id:
                return JsonResponse({
                    'status': 'success',
                    'history': [],
                    'message': '没有对话历史'
                })
            
            # 获取Agent实例和历史
            agent = get_control_agent()
            history = agent.get_conversation_history(session_id)
            
            return JsonResponse({
                'status': 'success',
                'history': history,
                'count': len(history)
            })
            
        except Exception as e:
            print(f"获取历史时出错: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': '获取历史失败'
            }, status=500)
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)


def AIagent_clear(request):
    """清空对话历史API"""
    if request.method == 'POST':
        try:
            # 获取session_id
            session_id = request.session.session_key
            if session_id:
                # 清空Agent中的会话
                agent = get_control_agent()
                agent.clear_session(session_id)
                
                # 清空Django session中的数据
                request.session.flush()
                
            return JsonResponse({
                'status': 'success',
                'message': '对话历史已清空'
            })
            
        except Exception as e:
            print(f"清空历史时出错: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': '清空历史失败'
            }, status=500)
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)


def get_fallback_response(message):
    """备用响应生成器"""
    message_lower = message.lower()
    
    # 基因相关的备用响应
    if any(keyword in message_lower for keyword in ['基因', 'gene', '分析', '靶点']):
        return """我理解您想进行基因分析。请告诉我：

1. 您想分析哪个基因？（例如：TP53, EGFR, BRCA1等）
2. 您关注的疾病领域是什么？
3. 您需要什么类型的分析？（靶点评估、药物开发潜力、专利分析等）

我会基于我们的对话历史，为您提供个性化的分析报告。"""
    
    # CRISPR相关的备用响应
    elif any(keyword in message_lower for keyword in ['crispr', 'cas9', 'sgrna', '编辑']):
        return """您提到了基因编辑技术。基于我们之前的讨论，我可以帮您：

• 设计sgRNA序列
• 评估脱靶效应
• 优化编辑效率
• 分析编辑结果

请告诉我具体的需求，我会结合之前的内容为您提供帮助。"""
    
    # 默认响应
    else:
        return """我是您的AI基因分析助手。我记得我们之前的对话内容，可以继续为您服务。

我可以帮您：
• **基因靶点分析** - 评估基因作为药物靶点的潜力
• **文献调研** - 搜索和分析相关研究文献  
• **专利分析** - 查询基因相关专利信息
• **药物开发评估** - 分析成药性和市场前景
• **CRISPR设计** - 协助基因编辑实验设计

您可以继续之前的话题，或告诉我新的分析需求。"""