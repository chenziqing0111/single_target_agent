# epigenicai_app/urls.py
from django.urls import path
from . import views
from django.shortcuts import redirect

urlpatterns = [
    # AI Agent 主页面
    path('AIagent/', views.AIagent_view, name='AIagent'),
    
    # AI Agent API端点
    path('AIagent/chat/', views.AIagent_chat, name='AIagent_chat'),
    path('AIagent/history/', views.AIagent_history, name='AIagent_history'),
    path('AIagent/clear/', views.AIagent_clear, name='AIagent_clear'),
     path('AIagent/status/', views.AIagent_status, name='AIagent_status'),
    
    # 重定向根路径到AIagent
    path('', lambda request: redirect('AIagent')),
]