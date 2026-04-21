from django.urls import path
from . import views

app_name = 'book'

urlpatterns = [
    # Pages
    path('',                   views.dashboard,    name='dashboard'),
    path('catalog/',           views.book_list,    name='book_list'),
    path('catalog/<int:pk>/',  views.book_detail,  name='book_detail'),
    path('catalog/add/',       views.book_add,     name='book_add'),
    path('catalog/<int:pk>/edit/',   views.book_edit,   name='book_edit'),
    path('catalog/<int:pk>/delete/', views.book_delete, name='book_delete'),

    # REST API
    path('api/books/',         views.book_api_list_create, name='api_books'),
    path('api/books/<int:pk>/', views.book_api_detail,     name='api_book_detail'),
    path('api/books/<int:book_id>/reviews/', views.api_book_reviews, name='api_book_reviews'),
    path('api/books/<int:book_id>/reviews/<int:review_id>/', views.api_delete_review, name='api_delete_review'),

    # AJAX / API
    path('api/enrich/',       views.api_enrich_isbn,  name='api_enrich_isbn'),
    path('api/search/',       views.api_search_title, name='api_search_title'),
    path('api/<int:pk>/',     views.api_book_detail,  name='api_book_detail'),
]