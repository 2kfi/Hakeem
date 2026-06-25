import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config import get_settings
from core.jwt_auth import get_jwt_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


class TokenRequest(BaseModel):
    api_key: str
    device_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(req: TokenRequest) -> TokenResponse:
    settings = get_settings()

    if settings.auth.disabled:
        key_config = {"permissions": ["*"]}
    elif settings.auth.api_keys:
        key_config = settings.auth.api_keys.get(req.api_key)
        if not key_config:
            raise HTTPException(status_code=401, detail="Invalid API key")
    else:
        key_config = {"permissions": ["*"]}

    device_id = req.device_id or key_config.get("device_id", "hakeem-cli")
    user_id = key_config.get("user_id", device_id)
    permissions = key_config.get("permissions", ["*"])

    mgr = get_jwt_manager()
    token = mgr.create_token(user_id=user_id, device_id=device_id, permissions=permissions)

    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt.expiry_minutes * 60,
    )
