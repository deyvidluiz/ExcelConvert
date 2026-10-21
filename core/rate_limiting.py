"""
Rate limiting por usuário e global.

Utiliza Redis (primário) ou cache Django (fallback) para controlar
rate limits de API e processamento.
"""

import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Optional

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Rate limit foi excedido."""
    def __init__(self, message="Rate limit exceeded", retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """
    Rate limiter configurável com Redis ou cache Django.
    
    Configurações por ambiente:
    - Development: usa cache local (não persistente)
    - Production: usa Redis (via django-redis)
    """
    
    # Limites padrão
    DEFAULTS = {
        "extractions_per_minute": 5,
        "extractions_per_hour": 30,
        "extractions_per_day": 100,
        "api_calls_per_minute": 20,
        "gemini_per_day_usd": 5.0,  # Limite em dólares
    }
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
    
    def _get_redis(self):
        """Obtém cliente Redis configurado."""
        if self.redis is not None:
            return self.redis
        
        # Tenta obter do django-redis
        try:
            from django_redis import get_redis_connection
            return get_redis_connection("default")
        except ImportError:
            return None
    
    def _use_redis(self) -> bool:
        """Verifica se Redis está disponível."""
        return self._get_redis() is not None and hasattr(settings, "CACHES") and settings.CACHES.get("default", {}).get("BACKEND", "").startswith("django_redis")
    
    def _make_key(self, key_type: str, identifier: str) -> str:
        """Gera chave para rate limit."""
        return f"ratelimit:{key_type}:{identifier}"
    
    def check_limit(self, key_type: str, identifier: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """
        Verifica se o limite foi atingido.
        
        Returns:
            Tuple (is_allowed, current_count)
        """
        key = self._make_key(key_type, identifier)
        
        if self._use_redis():
            return self._check_redis(key, limit, window_seconds)
        else:
            return self._check_cache(key, limit, window_seconds)
    
    def _check_redis(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Verifica limite usando Redis (atômico)."""
        redis = self._get_redis()
        if redis is None:
            return True, 0
        
        pipe = redis.pipeline()
        now = datetime.utcnow().timestamp()
        
        # Remove entradas antigas
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        
        # Conta atual
        pipe.zcard(key)
        
        # Adiciona nova request
        pipe.zadd(key, {str(now): now})
        
        # Define TTL
        pipe.expire(key, window_seconds)
        
        results = pipe.execute()
        current = results[1] if results[1] else 0
        
        return current < limit, current + 1
    
    def _check_cache(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Verifica limite usando cache Django (não atômico)."""
        now = datetime.utcnow()
        window_key = f"{key}:{now.minute // (window_seconds // 60)}"
        
        data = cache.get(window_key, {"count": 0, "start": now.isoformat()})
        current = data["count"]
        
        return current < limit, current + 1
    
    def increment(self, key_type: str, identifier: str, window_seconds: int = 60):
        """Incrementa contador (após verificação)."""
        key = self._make_key(key_type, identifier)
        
        if self._use_redis():
            redis = self._get_redis()
            now = datetime.utcnow().timestamp()
            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window_seconds)
            pipe.execute()
        else:
            window_key = f"{key}:{datetime.utcnow().minute // (window_seconds // 60)}"
            data = cache.get(window_key, {"count": 0})
            data["count"] += 1
            cache.set(window_key, data, window_seconds)
    
    def get_usage(self, key_type: str, identifier: str, window_seconds: int = 3600) -> dict:
        """Retorna usage atual para um identificador."""
        key = self._make_key(key_type, identifier)
        
        if self._use_redis():
            redis = self._get_redis()
            if redis:
                now = datetime.utcnow().timestamp()
                # Limpa antigos e conta
                redis.zremrangebyscore(key, 0, now - window_seconds)
                count = redis.zcard(key)
                return {"count": count, "limit": None}
        
        return {"count": 0, "limit": None}


# Instância global
rate_limiter = RateLimiter()


def rate_limit(
    key_type: str,
    limit: int,
    window_seconds: int = 60,
    by_user: bool = True,
    fallback_message: str = "Limite de requisições excedido. Tente novamente em {retry_after} segundos."
):
    """
    Decorator para aplicar rate limit a views.
    
    Args:
        key_type: Tipo de limite (e.g., 'extraction', 'api')
        limit: Número máximo de requests por window
        window_seconds: Janela de tempo em segundos
        by_user: Se True, limita por usuário; se False, global
        fallback_message: Mensagem personalizada
    """
    def decorator(view_func: Callable):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            identifier = str(request.user.id) if by_user and request.user.is_authenticated else "anonymous"
            
            is_allowed, current = rate_limiter.check_limit(key_type, identifier, limit, window_seconds)
            
            if not is_allowed:
                response_data = {
                    "error": "rate_limit_exceeded",
                    "message": fallback_message.format(retry_after=window_seconds),
                    "retry_after": window_seconds,
                    "current_usage": current,
                    "limit": limit,
                }
                
                # Adiciona header Retry-After
                response = JsonResponse(response_data, status=429)
                response["Retry-After"] = str(window_seconds)
                return response
            
            # Incrementa contador
            rate_limiter.increment(key_type, identifier, window_seconds)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class RateLimitMiddleware:
    """
    Middleware para tracking de limites globais.
    
    Usado para limits que não são aplicados via decorator
    (e.g., limite diário de API calls por usuário).
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Tracking de uso diário
            today_key = f"daily_usage:{request.user.id}:{datetime.utcnow().strftime('%Y%m%d')}"
            usage = cache.get(today_key, 0)
            
            # Adiciona ao request para views acessarem
            request.rate_limit_usage = {
                "daily_count": usage,
                "daily_limit": settings.MAX_MONTHLY_API_CALLS // 30 or 100,
            }
        
        response = self.get_response(request)
        
        # Atualiza contador no response
        if hasattr(request, "rate_limit_usage"):
            daily_key = f"daily_usage:{request.user.id}:{datetime.utcnow().strftime('%Y%m%d')}"
            new_count = request.rate_limit_usage.get("daily_count", 0) + 1
            cache.set(daily_key, new_count, 86400)  # 24 horas
        
        return response