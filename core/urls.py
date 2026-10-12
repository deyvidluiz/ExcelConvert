from django.contrib.auth import views as auth_views
from django.urls import path

from documentos import views as document_views
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("cadastro/", views.signup, name="signup"),
    path("processamento/<uuid:pk>/", document_views.process_document, name="processamento"),
    path("historico/", views.history, name="historico"),
    path("configuracoes/", views.settings_page, name="configuracoes"),
    path("health/", views.health, name="health"),
]
