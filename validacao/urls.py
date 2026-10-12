from django.urls import path

from . import views

app_name = "validacao"
urlpatterns = [path("<uuid:pk>/", views.editor, name="editor")]
