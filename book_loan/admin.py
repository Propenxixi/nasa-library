from django.contrib import admin
from .models import Loan, LoanExtension, WaitingList, Notification


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'book', 'status', 'loan_date', 'due_date', 'days_overdue')
    list_filter = ('status', 'loan_date', 'due_date')
    search_fields = ('user__first_name', 'book__title')
    readonly_fields = ('loan_date', 'approved_date', 'return_date', 'created_at', 'updated_at')
    ordering = ['-loan_date']


@admin.register(LoanExtension)
class LoanExtensionAdmin(admin.ModelAdmin):
    list_display = ('id', 'loan', 'status', 'requested_date', 'requested_duration')
    list_filter = ('status', 'requested_date')
    search_fields = ('loan__user__first_name', 'loan__book__title')
    readonly_fields = ('requested_date', 'approved_date', 'created_at', 'updated_at')
    ordering = ['-requested_date']


@admin.register(WaitingList)
class WaitingListAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'book', 'position', 'status', 'registered_date')
    list_filter = ('status', 'registered_date')
    search_fields = ('user__first_name', 'book__title')
    readonly_fields = ('registered_date', 'ready_date', 'created_at', 'updated_at')
    ordering = ['position', 'registered_date']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__first_name', 'title', 'message')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ['-created_at']
