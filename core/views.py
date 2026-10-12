import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render

from documentos.models import Document
from modelos.models import DocumentTemplate

from .forms import SignUpForm


@login_required
def dashboard(request):
    documents = Document.objects.filter(user=request.user)
    context = {
        "documents": documents[:6],
        "total_documents": documents.count(),
        "total_pages": documents.aggregate(total=Sum("page_count"))["total"] or 0,
        "total_tokens": documents.aggregate(total=Sum("token_count"))["total"] or 0,
        "input_tokens": documents.aggregate(total=Sum("input_token_count"))["total"] or 0,
        "output_tokens": documents.aggregate(total=Sum("output_token_count"))["total"] or 0,
        "api_calls": documents.aggregate(total=Sum("api_call_count"))["total"] or 0,
        "total_usd": documents.aggregate(total=Sum("estimated_cost_usd"))["total"] or 0,
        "total_brl": documents.aggregate(total=Sum("estimated_cost_brl"))["total"] or 0,
    }
    return render(request, "core/dashboard.html", context)


@login_required
def history(request):
    return render(request, "core/history.html", {"documents": Document.objects.filter(user=request.user)})


@login_required
def settings_page(request):
    return render(request, "core/settings.html", {"model": settings.GEMINI_MODEL, "has_key": bool(os.getenv("GEMINI_API_KEY")), "template_count": DocumentTemplate.objects.filter(is_active=True).count()})


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Conta criada com sucesso.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def health(request):
    return JsonResponse({"status": "ok", "service": "excelconvert"})
