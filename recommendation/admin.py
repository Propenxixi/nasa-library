from django.contrib import admin
from .models import UserPreference, Loan


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_categories_display', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    
    def get_categories_display(self, obj):
        if isinstance(obj.categories, list):
            return ', '.join(obj.categories[:3]) + ('...' if len(obj.categories) > 3 else '')
        return str(obj.categories)
    get_categories_display.short_description = 'Categories'


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'borrowed_at', 'due_date', 'returned_at', 'status']
    list_filter = ['status', 'borrowed_at']
    search_fields = ['user__username', 'book__title']
    date_hierarchy = 'borrowed_at'
