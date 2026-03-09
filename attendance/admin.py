from django.contrib import admin
from django.utils.html import format_html
from .models import Attendance, AttendanceActivity


@admin.register(AttendanceActivity)
class AttendanceActivityAdmin(admin.ModelAdmin):
    list_display = ['emoji_name', 'description', 'is_active', 'order']
    list_filter = ['is_active', 'order']
    search_fields = ['name', 'description']
    ordering = ['order', 'name']
    
    def emoji_name(self, obj):
        return f"{obj.emoji} {obj.name}"
    emoji_name.short_description = "Activity"
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'emoji', 'description')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
    )


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['get_student_name', 'check_in_time_display', 'status_badge', 'duration_display', 'get_activities']
    list_filter = ['status', 'check_in_time', 'activities']
    search_fields = ['user__first_name', 'user__last_name', 'user__username']
    readonly_fields = ['check_in_time', 'created_at', 'updated_at', 'duration_minutes', 'activity_list']
    date_hierarchy = 'check_in_time'
    
    fieldsets = (
        ('Student Information', {
            'fields': ('user',)
        }),
        ('Check-in/Check-out Times', {
            'fields': ('check_in_time', 'check_out_time'),
            'classes': ('collapse',)
        }),
        ('Activity Information', {
            'fields': ('activities', 'custom_activity')
        }),
        ('Status & Duration', {
            'fields': ('status', 'duration_minutes')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['activities']
    
    def get_student_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_student_name.short_description = "Student"
    
    def check_in_time_display(self, obj):
        return obj.check_in_time.strftime('%Y-%m-%d %H:%M')
    check_in_time_display.short_description = "Check-in Time"
    
    def status_badge(self, obj):
        colors = {
            'checked_in': 'green',
            'checked_out': 'blue',
            'auto_checked_out': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            {'green': '#10b981', 'blue': '#3b82f6', 'orange': '#f59e0b', 'gray': '#6b7280'}.get(color),
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    
    def get_activities(self, obj):
        activities = obj.activities.all()
        if activities:
            return ', '.join([str(a) for a in activities])
        return '-'
    get_activities.short_description = "Activities"
    
    def activity_list(self, obj):
        activities = obj.activities.all()
        custom = obj.custom_activity
        
        result = "<ul>"
        if activities:
            for activity in activities:
                result += f"<li>{activity.emoji} {activity.name}</li>"
        if custom:
            result += f"<li>✏️ {custom}</li>"
        if not activities and not custom:
            result += "<li>No activities recorded</li>"
        result += "</ul>"
        
        return format_html(result)
    activity_list.short_description = "Activities List"
    
    def has_delete_permission(self, request):
        # Prevent accidental deletion of attendance records
        return request.user.is_superuser
    
    actions = ['mark_as_checked_out']
    
    def mark_as_checked_out(self, request, queryset):
        from django.utils import timezone
        for record in queryset.filter(status='checked_in'):
            record.check_out_time = timezone.now()
            record.status = 'checked_out'
            record.save()
        self.message_user(request, f"{queryset.count()} records updated.")
    mark_as_checked_out.short_description = "Mark selected as checked out"

