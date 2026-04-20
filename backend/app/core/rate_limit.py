from fastapi import HTTPException, Request, status

from app.redis import redis_client


async def check_rate_limit(request: Request, key_prefix: str = "rl", max_requests: int = 100, window_seconds: int = 60):
    """Simple Redis-based rate limiter."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"{key_prefix}:{client_ip}"
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window_seconds)
    if current > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много запросов. Попробуйте позже.",
        )


async def check_login_rate_limit(request: Request):
    """Stricter rate limit for login: 5 attempts per 5 minutes."""
    await check_rate_limit(request, key_prefix="login_rl", max_requests=5, window_seconds=300)
