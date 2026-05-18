"""
URL configuration for nasa_library project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from literacy import views as literacy_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('authentication.urls')),
    path('attendance/', include('attendance.urls')),
    path('literacy/', include('literacy.urls')),
    path('api/literacy/leaderboard/', literacy_views.api_leaderboard, name='root_api_leaderboard'),
    path('api/literacy/scores', literacy_views.api_scores, name='root_api_scores'),
    path('', include('main.urls')),
    path('book/', include('book.urls')),
    path('loan/', include('book_loan.urls')),
    path('recommendation/', include('recommendation.urls')),
    path('book-request/', include('book_request.urls')),
    path("users/", include("user.urls", namespace="user")),
    path('report/', include('report.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('api/dashboard/', include('dashboard.api_urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
