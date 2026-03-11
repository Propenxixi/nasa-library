from django.urls import path
from . import views

app_name = "book_request"

urlpatterns = [
    # Entry point – routes staff to dashboard, students/teachers to history
    path("", views.request_list_view, name="request_list"),

    # Student / Teacher – halaman
    path("create/", views.request_create_view, name="request_create"),
    path("success/<int:pk>/", views.request_success_view, name="request_success"),
    path("api/mark-seen/", views.mark_notifications_seen, name="mark_seen"),

    # Staff / Petugas – halaman
    path("staff/", views.staff_dashboard_view, name="staff_dashboard"),
    path("staff/review/<int:pk>/", views.staff_review_view, name="staff_review"),
]