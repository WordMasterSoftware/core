from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, UserSession
from app.utils.auth import decode_token
from datetime import datetime
import uuid as uuid_pkg

# 定义 Bearer Token 安全方案
security = HTTPBearer(
    scheme_name="Bearer",
    description="请输入 JWT Token (从登录或注册接口获取)"
)


from app.config import settings

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> User:
    """获取当前登录用户"""
    token = credentials.credentials

    # Development Backdoor: Allow access with DEV_TOKEN from .env
    if settings.DEBUG and settings.DEV_TOKEN and token == settings.DEV_TOKEN:
        # Get the first user or a default admin user
        user = session.exec(select(User)).first()
        if user:
            return user
        # If no user exists, we can't return a valid user object, so we fall through to normal auth
        # or maybe raise a specific error saying "Create a user first"

    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证会话是否存在且未过期
    statement = select(UserSession).where(
        UserSession.user_id == uuid_pkg.UUID(user_id),
        UserSession.expires_at > datetime.utcnow()
    )
    user_session = session.exec(statement).first()
    
    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 获取用户信息
    user = session.get(User, uuid_pkg.UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user
