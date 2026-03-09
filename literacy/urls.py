from django.urls import path
from . import views

app_name = 'literacy'

urlpatterns = [
    # Student Review Submission
    path('submit-review/', views.submit_review_view, name='submit_review'),
    path('my-reviews/', views.my_reviews_view, name='my_reviews'),
    path('reviews/<int:pk>/', views.review_detail_view, name='review_detail'),
    
    # Leaderboard
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    
    # Teacher Verification
    path('teacher/verify/', views.teacher_verify_reviews_view, name='teacher_verify_reviews'),
    path('teacher/verify/<int:pk>/', views.verify_review_view, name='verify_review'),
    
    # Forum/Posts
    path('forum/', views.forum_view, name='forum'),
    path('forum/create/', views.create_post_view, name='create_post'),
    path('forum/<int:pk>/', views.post_detail_view, name='post_detail'),
    path('forum/<int:pk>/delete/', views.delete_post_view, name='delete_post'),
]
