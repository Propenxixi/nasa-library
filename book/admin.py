from django.contrib import admin
from .models import Book, Review


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display  = ('title', 'author', 'isbn', 'status', 'total_copies', 'available_copies', 'created_at')
    list_filter   = ('status', 'language')
    search_fields = ('title', 'author', 'isbn', 'category')
    readonly_fields = ('created_at', 'updated_at', 'updated_by')
    fieldsets = (
        ('Informasi Dasar', {
            'fields': ('title', 'author', 'isbn', 'pages', 'language')
        }),
        ('Stok & Lokasi', {
            'fields': ('total_copies', 'shelf_location', 'status')
        }),
        ('Data Enriched (dari API)', {
            'fields': ('cover_url', 'publisher', 'publish_year', 'category', 'synopsis'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ('book', 'user', 'rating', 'created_at')
    list_filter   = ('rating',)
    search_fields = ('book__title', 'user__username')