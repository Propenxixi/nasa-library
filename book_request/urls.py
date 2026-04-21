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
    path("check-duplicate/", views.check_duplicate_view, name="check_duplicate"),

    # Staff / Petugas – halaman
    path("staff/", views.staff_dashboard_view, name="staff_dashboard"),
    path("staff/review/<int:pk>/", views.staff_review_view, name="staff_review"),

    # API Endpoints
    path("api/books/proposals", views.api_create_proposal, name="api_create_proposal"),
    path("api/books/proposals/my-proposals", views.api_my_proposals, name="api_my_proposals"),
    path("api/books/proposals/pending", views.api_pending_proposals, name="api_pending_proposals"),
    path("api/books/proposals/<int:pk>/review", views.api_review_proposal, name="api_review_proposal"),
]