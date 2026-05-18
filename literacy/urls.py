from django.urls import path
from . import views
from .views import history_view

app_name = 'literacy'

urlpatterns = [
    # Siswa
    path('submit-review/', views.submit_review_view, name='submit_review'),
    path('history/', history_view, name='history'),
    path('reviews/<int:pk>/', views.review_detail_view, name='review_detail'),

    # Submit review baru
    # POST /api/literacy/reviews  →  201 Created / 400 Bad Request
    path('api/literacy/reviews', views.submit_review_api, name='api_submit_review'),

    # Riwayat review siswa
    # Dipanggil JS di forum.html via fetch('/api/literacy/reviews/my-reviews')
    path('api/literacy/reviews/my-reviews', views.my_reviews_api, name='my_reviews_api'),

    # Rekap Data Literasi
    path('recap/', views.recap_view, name='recap'),
    path('api/literacy/recap', views.recap_api, name='api_recap'),

    # ── Leaderboard (PBI-28) ────────────────────────────────────────────────
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    # Note: API Leaderboard & Scores moved to root urls.py for PBI-27 compliance


    # Guru — Verifikasi Review
    # Halaman daftar review pending; aksi dilakukan via API di bawah
    path('teacher/verify/', views.teacher_verify_reviews_view, name='teacher_verify_reviews'),

    # Daftar review pending (GET) dan verifikasi (PUT)
    path('api/literacy/reviews/pending', views.pending_reviews_api, name='api_pending_reviews'),
    path('api/literacy/reviews/<int:id>/verify', views.verify_review_api, name='api_verify_review'),

    # Forum — Sesi
    path('forum/', views.forum_view, name='forum'),
    path('forum/sesi/buat/', views.create_session_view, name='create_session'),
    path('forum/sesi/<int:pk>/', views.session_detail_view, name='session_detail'),

    # Forum — Posts
    path('forum/create/', views.create_post_view, name='create_post'),
    path('forum/<int:pk>/', views.post_detail_view, name='post_detail'),
    # Buat forum posting via JSON
    # POST /api/literacy/forum/posts  →  201 Created / 400 Bad Request
    path('api/literacy/forum/posts', views.create_forum_post_api, name='api_create_forum_post'),

    # Riwayat postingan forum milik siswa yang login
    # GET /api/literacy/forum/posts/my-posts  →  200 OK (dipakai forum.html)
    path('api/literacy/forum/posts/my-posts', views.my_forum_posts_api, name='my_forum_posts_api'),

]