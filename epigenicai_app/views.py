# epigenicai_app/views.py
"""
优化后的Django视图 - 纯粹的Web层和Session管理
"""
import json
import asyncio
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from threading import Thread

def AIagent_view(request):
    """AI助手主页面视图"""
    if request.method == 'GET':
        return render(request, 'AIagent.html')
    else:
        return HttpResponse("Method not allowed", status=405)



@csrf_exempt
def AIagent_chat(request):
    """
    支持普通对话 + 异步后台分析任务
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        # 1️⃣ 解析请求
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        if not message:
            return JsonResponse({'status': 'error', 'message': '消息不能为空'}, status=400)

        # 2️⃣ Session 与上下文
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        messages_history = request.session.get('messages', [])
        messages_history.append({"role": "user", "content": message})

        context = {
            'session_id': session_key,
            'current_gene': request.session.get('current_gene'),
            'task_id': request.session.get('task_id'),
            'task_start_time': request.session.get('task_start_time'),
        }

        # 3️⃣ 创建 agent 并同步分析一次（看看用户说的内容属于哪类任务）
        from agent_core.agents.control_agent import ControlAgent
        agent = ControlAgent()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(agent.process_message(message, messages_history, context))
        loop.close()

        # 更新消息历史（先加上回复）
        if result.get("message_to_add"):
            messages_history.append(result["message_to_add"])
        else:
            messages_history.append({"role": "assistant", "content": result.get("message", "")})
        request.session["messages"] = messages_history
        request.session.modified = True
        request.session.save()

        # 4️⃣ 如果是后台分析任务，就开线程执行（不阻塞主线程）
        if result.get("type") == "analyzing":
            gene = result.get("gene")
            task_id = result.get("task_id", f"{gene}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            request.session["task_id"] = task_id
            request.session["current_gene"] = gene
            request.session["task_start_time"] = datetime.now().isoformat()
            request.session.save()

            def run_background_analysis():
                try:
                    asyncio.run(agent._run_analysis(gene, task_id))
                except Exception as e:
                    print(f"[Thread] 后台分析出错: {e}")
                    agent.cache_set(f"task_status_{task_id}", f"error: {e}")

            Thread(target=run_background_analysis, daemon=True).start()

        response_data = {
            "status": 'success',
            "response": result.get("message", ""),
            "conversation_count": len(messages_history),
            'type': result.get('type', 'chat'),
            "session_id": session_key
        }

        if result.get("gene"):
            response_data["gene"] = result["gene"]
        if result.get("confidence"):
            response_data["confidence"] = result["confidence"]

        return JsonResponse(response_data)

    except Exception as e:
        print(f"[Error] 处理请求失败: {e}")
        import traceback; traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



def AIagent_history(request):
    """获取对话历史"""
    if request.method != 'GET':
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        # 获取对话历史
        messages = request.session.get('messages', [])
        
        # 格式化历史（方便前端展示）
        formatted_history = []
        for msg in messages:
            formatted_history.append({
                'role': msg['role'],
                'content': msg['content'],
                'timestamp': msg.get('timestamp', '')
            })
        
        return JsonResponse({
            'status': 'success',
            'history': formatted_history,
            'count': len(formatted_history),
            'current_gene': request.session.get('current_gene'),
            'task_id': request.session.get('task_id')
        })
        
    except Exception as e:
        print(f"获取历史记录失败: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': '获取历史记录失败'
        }, status=500)


def AIagent_clear(request):
    """清空对话历史和重置会话"""
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        # 清空所有session数据
        session_keys_to_clear = [
            'messages',
            'current_gene',
            'task_id',
            'task_start_time'
        ]
        
        for key in session_keys_to_clear:
            request.session.pop(key, None)
        
        request.session.modified = True
        request.session.save()
        
        return JsonResponse({
            'status': 'success',
            'message': '对话历史已清空，可以开始新的分析'
        })
        
    except Exception as e:
        print(f"清空对话历史失败: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': '清空失败',
            'details': str(e) if request.GET.get('debug') else None
        }, status=500)


def AIagent_status(request):
    """检查分析任务状态"""
    if request.method != 'GET':
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        task_id = request.session.get('task_id')
        
        if not task_id:
            return JsonResponse({
                'status': 'success',
                'task_status': 'no_task',
                'message': '没有正在运行的任务'
            })
        
        # 使用Agent的缓存方法获取任务状态
        from agent_core.agents.control_agent import ControlAgent
        agent = ControlAgent()
        task_status = agent.cache_get(f"task_status_{task_id}")
        
        response_data = {
            'status': 'success',
            'task_id': task_id,
            'task_status': task_status or 'unknown',
            'current_gene': request.session.get('current_gene')
        }
        
        # 如果任务完成，检查是否有报告
        if task_status == 'completed':
            gene = request.session.get('current_gene')
            if gene:
                report = agent.get_cached_report(gene)
                if report:
                    response_data['report_url'] = report.get('report_url')
                    response_data['generated_at'] = report.get('generated_at')
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"检查任务状态失败: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': '检查状态失败'
        }, status=500)


def AIagent_refresh_cache(request):
    """强制刷新基因分析缓存"""
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        data = json.loads(request.body)
        gene = data.get('gene')
        
        if not gene:
            return JsonResponse({
                'status': 'error',
                'message': '请提供基因名称'
            }, status=400)
        
        # 使用Agent的方法清除缓存
        from agent_core.agents.control_agent import ControlAgent
        agent = ControlAgent()
        success = agent.clear_gene_cache(gene)
        
        if success:
            return JsonResponse({
                'status': 'success',
                'message': f'{gene}基因的缓存已清除，下次分析将重新生成报告'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': '清除缓存失败'
            }, status=500)
        
    except Exception as e:
        print(f"清除缓存失败: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': '清除缓存失败'
        }, status=500)


def AIagent_cache_status(request):
    """获取缓存状态信息（新增）"""
    if request.method != 'GET':
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        from agent_core.agents.control_agent import ControlAgent
        agent = ControlAgent()
        cache_status = agent.get_cache_status()
        
        return JsonResponse({
            'status': 'success',
            'cache_info': cache_status
        })
        
    except Exception as e:
        print(f"获取缓存状态失败: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': '获取缓存状态失败'
        }, status=500)