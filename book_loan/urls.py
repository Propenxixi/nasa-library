from django.urls import path
from . import views

app_name = 'book_loan'

urlpatterns = [
    # Pages
    path('history/', views.loan_history, name='loan_history'),
    path('waiting-list/', views.waiting_list_view, name='waiting_list'),
    path('management/', views.loan_management, name='loan_management'),
    
    # API - Loans
    path('api/loans/', views.api_list_loans, name='api_list_loans'),
    path('api/loans/create/', views.api_create_loan, name='api_create_loan'),
    path('api/loans/<int:loan_id>/approve/', views.api_approve_loan, name='api_approve_loan'),
    path('api/loans/<int:loan_id>/reject/', views.api_reject_loan, name='api_reject_loan'),
    path('api/loans/<int:loan_id>/return/', views.api_return_loan, name='api_return_loan'),
    path('api/loans/<int:loan_id>/extend/', views.api_request_extension, name='api_request_extension'),
    path('api/loans/<int:loan_id>/approve-extend/', views.api_approve_extension, name='api_approve_extension'),
    path('api/loans/<int:loan_id>/reject-extend/', views.api_reject_extension, name='api_reject_extension'),
    path('api/loans/active/', views.api_get_active_loans, name='api_get_active_loans'),
    
    # API - Waiting List
    path('api/waitlist/create/', views.api_create_waiting_list, name='api_create_waiting_list'),
    path('api/waitlist/my-list/', views.api_my_waiting_list, name='api_my_waiting_list'),
    path('api/waitlist/<int:waiting_id>/cancel/', views.api_cancel_waiting_list, name='api_cancel_waiting_list'),
    path('api/waitlist/<int:waiting_id>/claim/', views.api_claim_waiting_list, name='api_claim_waiting_list'),
    
    # API - Notifications
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
    path('api/notifications/<int:notification_id>/read/', views.api_mark_notification_read, name='api_mark_notification_read'),
]
