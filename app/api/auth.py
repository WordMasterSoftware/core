"""认证相关API"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_session
from app.schemas.auth import (
    UserRegister, UserLogin, UserResponse, AuthResponse,
    TokenResponse, ProfileUpdate, PasswordChange, RefreshTokenRequest,
    LLMConfigUpdate, LLMConfigResponse
)
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user
from app.models import User
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 获取速率限制器
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(
    request: Request,
    user_data: UserRegister,
    session: Session = Depends(get_session)
):
    """用户注册"""
    try:
        user, access_token, refresh_token = await AuthService.register_user(user_data, session)
        
        return AuthResponse(
            success=True,
            message="注册成功",
            data={
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "nickname": user.nickname,
                "use_default_llm": user.use_default_llm,
                "token": access_token,
                "refresh_token": refresh_token,
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        )
    except HTTPException as e:
        return AuthResponse(
            success=False,
            message=e.detail,
            error_code="REGISTRATION_FAILED"
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    login_data: UserLogin,
    session: Session = Depends(get_session)
):
    """用户登录"""
    try:
        user, access_token, refresh_token = await AuthService.login_user(login_data, session)
        
        return AuthResponse(
            success=True,
            message="登录成功",
            data={
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "use_default_llm": user.use_default_llm,
                "token": access_token,
                "refresh_token": refresh_token,
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        )
    except HTTPException as e:
        return AuthResponse(
            success=False,
            message=e.detail,
            error_code="INVALID_CREDENTIALS"
        )


@router.post("/logout", response_model=AuthResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """退出登录"""
    await AuthService.logout_user(current_user, session)
    return AuthResponse(
        success=True,
        message="退出成功"
    )


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    return AuthResponse(
        success=True,
        message="获取成功",
        data={
            "user_id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
            "nickname": current_user.nickname,
            "avatar_url": current_user.avatar_url,
            "use_default_llm": current_user.use_default_llm,
            "llm_base_url": current_user.llm_base_url if not current_user.use_default_llm else None,
            "llm_model": current_user.llm_model if not current_user.use_default_llm else None,
            "created_at": current_user.created_at.isoformat(),
            "last_login_time": current_user.last_login_time.isoformat() if current_user.last_login_time else None
        }
    )


@router.put("/profile", response_model=AuthResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """更新用户资料"""
    if profile_data.nickname:
        current_user.nickname = profile_data.nickname
    if profile_data.avatar_url:
        current_user.avatar_url = profile_data.avatar_url
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    return AuthResponse(
        success=True,
        message="更新成功",
        data={
            "user_id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
            "nickname": current_user.nickname,
            "avatar_url": current_user.avatar_url
        }
    )


@router.put("/password", response_model=AuthResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """修改密码"""
    from app.utils.auth import verify_password, get_password_hash
    
    if not verify_password(password_data.old_password, current_user.password_hash):
        return AuthResponse(
            success=False,
            message="原密码错误",
            error_code="INVALID_OLD_PASSWORD"
        )
    
    current_user.password_hash = get_password_hash(password_data.new_password)
    session.add(current_user)
    session.commit()
    
    return AuthResponse(
        success=True,
        message="密码修改成功"
    )


# ============ LLM 配置管理 ============

@router.get("/llm-config", response_model=AuthResponse)
async def get_llm_config(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的LLM配置"""
    return AuthResponse(
        success=True,
        message="获取成功",
        data={
            "use_default_llm": current_user.use_default_llm,
            "llm_base_url": current_user.llm_base_url if not current_user.use_default_llm else settings.DEFAULT_LLM_BASE_URL,
            "llm_model": current_user.llm_model if not current_user.use_default_llm else settings.DEFAULT_LLM_MODEL,
            # 不返回 API Key（安全考虑）
            "has_custom_api_key": bool(current_user.llm_api_key) if not current_user.use_default_llm else False
        }
    )


@router.put("/llm-config", response_model=AuthResponse)
async def update_llm_config(
    config: LLMConfigUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    更新用户的LLM配置
    
    - use_default_llm=True: 使用系统默认配置（.env中的配置）
    - use_default_llm=False: 使用用户自定义配置，需提供 api_key, base_url, model
    """
    # 更新配置
    current_user.use_default_llm = config.use_default_llm
    
    if not config.use_default_llm:
        # 使用自定义配置
        if not config.llm_api_key:
            return AuthResponse(
                success=False,
                message="使用自定义LLM配置时，API Key为必填项",
                error_code="MISSING_API_KEY"
            )
        
        current_user.llm_api_key = config.llm_api_key
        current_user.llm_base_url = config.llm_base_url or settings.DEFAULT_LLM_BASE_URL
        current_user.llm_model = config.llm_model or settings.DEFAULT_LLM_MODEL
    else:
        # 使用默认配置，清空自定义配置
        current_user.llm_api_key = None
        current_user.llm_base_url = None
        current_user.llm_model = None
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    return AuthResponse(
        success=True,
        message="LLM配置更新成功",
        data={
            "use_default_llm": current_user.use_default_llm,
            "llm_base_url": current_user.llm_base_url or settings.DEFAULT_LLM_BASE_URL,
            "llm_model": current_user.llm_model or settings.DEFAULT_LLM_MODEL
        }
    )
