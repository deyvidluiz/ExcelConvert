from django.urls import path

from . import views

app_name = "exportacao"
urlpatterns = [path("<uuid:pk>/<str:format>/", views.download, name="download")]
