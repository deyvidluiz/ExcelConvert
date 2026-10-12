from django.conf import settings


def app_settings(request):
    return {
        "settings": {
            "MAX_UPLOAD_SIZE_MB": settings.MAX_UPLOAD_SIZE_MB,
            "MAX_DOCUMENT_PAGES": settings.MAX_DOCUMENT_PAGES,
            "MAX_MONTHLY_ESTIMATED_USD": settings.MAX_MONTHLY_ESTIMATED_USD,
            "USD_TO_BRL": settings.USD_TO_BRL,
        }
    }
