from django.contrib import admin
from .models import BookReview, LiteracyPost, LiteracySession, LiteracyLeaderboard

@admin.register(BookReview)
class BookReviewAdmin(admin.ModelAdmin):
    list_display = ('title', 'student', 'status', 'verified_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'student__username', 'student__first_name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LiteracySession)
class LiteracySessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'date', 'is_open')
    list_filter = ('topic', 'is_open', 'date')
    search_fields = ('title',)

@admin.register(LiteracyPost)
class LiteracyPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'student', 'session', 'verification_status', 'verified_at')
    list_filter = ('verification_status', 'created_at')
    search_fields = ('title', 'student__username', 'content')

@admin.register(LiteracyLeaderboard)
class LiteracyLeaderboardAdmin(admin.ModelAdmin):
    list_display = ('student', 'month', 'year', 'total_score', 'rank')
    list_filter = ('month', 'year', 'rank')
    search_fields = ('student__username', 'student__first_name')
