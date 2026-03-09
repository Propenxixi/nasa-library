from django.urls import path

from main.views import show_mainpage

app_name = 'main'

urlpatterns = [
    path('', show_mainpage, name='mainpage'),
]