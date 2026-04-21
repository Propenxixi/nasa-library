from django.urls import path
from . import views

app_name = 'report'

urlpatterns = [
    path('', views.report_page_view, name='index'),
    path('api/preview/', views.api_report_preview, name='api_preview'),
    path('api/export/', views.api_report_export, name='api_export'),
]
