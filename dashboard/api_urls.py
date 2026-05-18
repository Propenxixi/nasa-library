from django.urls import path
from . import views

urlpatterns = [
    path('', views.api_dashboard, name='api_dashboard'),
    path('loan-chart/', views.api_loan_chart, name='api_loan_chart'),
    path('popular-categories/', views.api_popular_categories, name='api_popular_categories'),
    path('recent-activity/', views.api_recent_activity, name='api_recent_activity'),

    path('visitors/summary/', views.api_visitors_summary, name='api_visitors_summary'),
    path('visitors/trend/', views.api_visitors_trend, name='api_visitors_trend'),
    path('visitors/activity/', views.api_visitors_activity, name='api_visitors_activity'),
    path('visitors/popular-activities/', views.api_visitors_popular_activities, name='api_visitors_popular_activities'),
]