from django.urls import path
from . import views

app_name = 'recommendation'

urlpatterns = [
    # Preference endpoints - combined view
    path('api/users/preferences', views.preferences_view, name='preferences'),
    path('api/users/preferences/check', views.check_preferences, name='check_preferences'),
    
    # Categories
    path('api/categories', views.get_categories, name='get_categories'),
    
    # Recommendations
    path('api/books/recommendations/personalized', views.get_personalized_recommendations, name='personalized_recommendations'),
    path('api/books/recommendations', views.get_popular_recommendations, name='popular_recommendations'),
]
