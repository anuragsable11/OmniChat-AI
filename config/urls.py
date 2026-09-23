"""
URL configuration for the OmniChat AI project.

The landing page is served at the root, the chat app under /chat/
and the REST API under /api/.
"""
from django.contrib import admin
from django.urls import include, path

from chat.views import chat_page, landing_page, login_page, logout_page


urlpatterns = [
    path("admin/", admin.site.urls),

    path("", landing_page, name="landing_page"),
    path("chat/", chat_page, name="chat_page"),
    path("login/", login_page, name="login_page"),
    path("logout/", logout_page, name="logout_page"),

    path("api/", include("chat.urls")),
]
