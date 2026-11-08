from django.contrib import admin
from django.urls import path

from links import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("links/", views.link_list, name="link_list"),
    path("links/new/", views.link_create, name="link_create"),
    path("links/<int:pk>/delete/", views.link_delete, name="link_delete"),
    path("<slug:code>/", views.follow_link, name="follow_link"),
    path("", views.home, name="home"),
]
