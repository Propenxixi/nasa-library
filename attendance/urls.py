from django.urls import path
from .views import (
    check_in_view,
    active_attendance_view,
    dashboard_view,
    auto_checkout_view,
    attendance_history_view,
    report_view,
    api_checkin,
    api_checkout,
    api_report,
)

app_name = 'attendance'

urlpatterns = [
    # Web pages
    path('check-in/', check_in_view, name='check_in'),
    path('active/', active_attendance_view, name='active_attendance'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('report/', report_view, name='report'),
    path('auto-checkout/<int:record_id>/', auto_checkout_view, name='auto_checkout'),
    path('history/', attendance_history_view, name='history'),
    
    # API endpoints
    path('api/checkin', api_checkin, name='api_checkin'),
    path('api/checkout', api_checkout, name='api_checkout'),
    path('api/report', api_report, name='api_report'),
]
