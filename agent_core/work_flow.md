第一步：初始化 Django 项目
conda activate agent_env  # 你的环境名
django-admin startproject django_project
cd django_project
python manage.py startapp api

第二步：配置 Django

编辑 django_project/settings.py：
INSTALLED_APPS = [
    ...
    'api',
    'corsheaders',  # 如果你需要跨域支持
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    ...
]

# 可选，允许本地测试跨域请求
CORS_ORIGIN_ALLOW_ALL = True


第三步：创建一个 Agent 接口视图
#api/views.py
from django.http import JsonResponse
from agent_core.control_agent import dispatch_task  # 你自己的主控 Agent 模块

def run_agent_task(request):
    gene = request.GET.get('gene', '')
    user_prefs = request.GET.get('preferences', '')

    result = dispatch_task(gene, user_prefs)
    return JsonResponse(result, safe=False)

#api/urls.py

from django.urls import path
from .views import run_agent_task

urlpatterns = [
    path('run/', run_agent_task),
]

#django_project/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]


