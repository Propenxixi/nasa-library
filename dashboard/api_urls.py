from django.urls import path
from . import views

urlpatterns = [
    path('', views.api_dashboard, name='api_dashboard'),
    path('loan-chart/', views.api_loan_chart, name='api_loan_chart'),
    path('popular-categories/', views.api_popular_categories, name='api_popular_categories'),
    path('recent-activity/', views.api_recent_activity, name='api_recent_activity'),
]