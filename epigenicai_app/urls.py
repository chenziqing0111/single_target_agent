from django.urls import path
from . import views

urlpatterns = [
    # 新的聊天界面
    path('', views.chat_home, name='chat_home'),  # 聊天主页
    path('chat/', views.chat_home, name='chat'),  # 聊天界面（兼容）
    
    # API端点
    path('api/chat/', views.chat_api, name='chat_api'),  # 聊天API
    path('api/task-status/<str:task_id>/', views.task_status_api, name='task_status_api'),  # 任务状态API
    path('api/report/<str:task_id>/', views.report_api, name='report_api'),  # 报告API
    
    # 保留原有端点作为备份
    path('index/', views.index, name='index'),  # 原首页
    path('old-chat/', views.chat, name='old_chat'),  # 原聊天处理
]
