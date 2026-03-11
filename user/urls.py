from django.urls import path
from . import views
from . import api_views

app_name = "user"

urlpatterns = [
    # Web views
    path("", views.user_list, name="user_list"),
    path("add/", views.user_create, name="user_create"),
    path("<int:user_id>/edit/", views.user_update, name="user_update"),
    path("<int:user_id>/deactivate/", views.user_deactivate, name="user_deactivate"),
    path("<int:user_id>/activate/", views.user_activate, name="user_activate"),

    # REST API
    path("api/users/", api_views.api_user_list_create, name="api_user_list_create"),
    path("api/users/<int:user_id>/", api_views.api_user_detail, name="api_user_detail"),
]