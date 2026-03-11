from django.contrib import admin
from django.utils.html import format_html
from .models import BookRequest


@admin.register(BookRequest)
class BookRequestAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'author', 'category',
        'requester_name', 'status_badge',
        'created_at', 'reviewed_by',
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'title', 'author', 'category',
        'requester__first_name', 'requester__last_name', 'requester__username',
    ]
    readonly_fields = ['created_at', 'updated_at', 'requester', 'notification_seen']
    ordering = ['-created_at']

    fieldsets = (
        ('Detail Usulan', {
            'fields': ('requester', 'title', 'author', 'publisher', 'category', 'reason'),
        }),
        ('Tinjauan', {
            'fields': ('status', 'reviewed_by', 'catatan_petugas'),
        }),
        ('Metadata', {
            'fields': ('notification_seen', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def requester_name(self, obj):
        return obj.requester.get_full_name() or obj.requester.username
    requester_name.short_description = 'Pengaju'

    def status_badge(self, obj):
        colors = {
            'pending':  ('#f59e0b', '#fffbeb'),
            'approved': ('#10b981', '#ecfdf5'),
            'rejected': ('#ef4444', '#fef2f2'),
        }
        text_color, bg_color = colors.get(obj.status, ('#6b7280', '#f9fafb'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:4px;font-weight:600;">{}</span>',
            bg_color, text_color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        """Auto-fill reviewed_by when admin changes status away from pending."""
        if change and obj.status in ('approved', 'rejected') and not obj.reviewed_by:
            obj.reviewed_by = request.user
        # Reset notification_seen so requester gets the pop-up
        if change and 'status' in form.changed_data:
            obj.notification_seen = False
        super().save_model(request, obj, form, change)