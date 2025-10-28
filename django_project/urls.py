# django_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve
from django.urls import re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('epigenicai_app.urls')),  # 包含app的URL
    re_path(r'^reports/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'reports'}),

]