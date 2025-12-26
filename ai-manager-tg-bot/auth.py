import aiohttp
import logging
from fastapi import HTTPException, Depends, Request
from typing import Optional

# Конфигурация сервиса аутентификации
AUTH_SERVICE_BASE_URL = "http://109.172.36.219:8000"
CHECK_PERMISSIONS_URL = f"{AUTH_SERVICE_BASE_URL}/api/auth/me"

async def check_permissions(token: str) -> bool:
    """
    Проверяет разрешения пользователя через сервис аутентификации
    
    Args:
        token: JWT токен
    
    Returns:
        bool: True если пользователь авторизован и является администратором (is_admin==True)
    """
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(CHECK_PERMISSIONS_URL, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # Возвращаем True если is_admin==True
                    return data.get("is_admin", False)
                else:
                    logging.warning(f"Permission check failed: {response.status}")
                    return False
    except Exception as e:
        logging.error(f"Error checking permissions: {e}")
        return False

async def get_token_from_header(request: Request) -> Optional[str]:
    """
    Извлекает JWT токен из заголовка Authorization
    
    Args:
        request: FastAPI Request объект
    
    Returns:
        str: JWT токен или None если не найден
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    return authorization.replace("Bearer ", "")

async def verify_token(request: Request) -> bool:
    """
    Проверяет JWT токен и разрешения пользователя
    
    Args:
        request: FastAPI Request объект
    
    Returns:
        bool: True если токен валиден и пользователь имеет разрешения
    """
    token = await get_token_from_header(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")
    
    is_authorized = await check_permissions(token)
    if not is_authorized:
        raise HTTPException(status_code=401, detail="Invalid token or insufficient permissions")
    
    return True

# Dependency для использования в эндпоинтах
async def require_auth(request: Request) -> bool:
    """
    Dependency для проверки аутентификации в эндпоинтах
    """
    return await verify_token(request) 