from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("documentos/", include("documentos.urls")),
    path("extracao/", include("extracao.urls")),
    path("validacao/", include("validacao.urls")),
    path("exportacao/", include("exportacao.urls")),
]
