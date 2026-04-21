from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "User Profile"
    fieldsets = (
        ('Informasi Dasar', {
            'fields': ('role', 'nis', 'gender', 'kelas')
        }),
        ('Status Aktif', {
            'fields': ('is_active_student', 'deactivation_reason', 'deactivated_at')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('deactivated_at', 'created_at', 'updated_at')


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('nis', 'get_full_name', 'role', 'kelas', 'is_active_student', 'deactivation_reason')
    list_filter = ('role', 'is_active_student', 'deactivation_reason', 'created_at')
    search_fields = ('nis', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'deactivated_at')
    fieldsets = (
        ('User Account', {
            'fields': ('user',)
        }),
        ('Informasi Dasar', {
            'fields': ('role', 'nis', 'gender', 'kelas')
        }),
        ('Status Aktif', {
            'fields': ('is_active_student', 'deactivation_reason', 'deactivated_at')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Nama Lengkap'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
