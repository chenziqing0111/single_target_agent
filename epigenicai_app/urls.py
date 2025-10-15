# epigenicai_app/urls.py
from django.urls import path
from . import views
from django.shortcuts import redirect
urlpatterns = [
    # 使用已存在的index视图作为主页
    # path('', views.index, name='index'),
    
    # API端点
    path('AIagent/', views.AIagent_view, name='AIagent'),
    path('AIagent/chat/', views.AIagent_chat, name='AIagent_chat'),
    
    # 如果你想保留其他URL（可选）
    # path('chat/', views.chat, name='chat'),  # 如果有chat视图
    path('', lambda request: redirect('AIagent')),
]