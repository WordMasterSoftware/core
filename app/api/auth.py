"""
认证相关 API 接口

该模块提供用户认证功能：
- 用户注册（带 IP 速率限制）
- 用户登录/登出
- 获取/更新用户信息
- 密码修改
- LLM 配置管理
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session

from app.config import settings
from app.database import get_session
from app.models import User
from app.schemas.auth import (
    AuthResponse,
    LLMConfigUpdate,
    PasswordChange,
    ProfileUpdate,
    UserLogin,
    UserRegister,
)
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 速率限制器，基于客户端 IP 地址
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(
    request: Request,
    user_data: UserRegister,
    session: Session = Depends(get_session)
) -> AuthResponse:
    """
    用户注册

    同一 IP 地址每分钟最多 10 次请求

    Args:
        request: FastAPI 请求对象（用于速率限制获取 IP）
        user_data: 注册信息（用户名、邮箱、密码）
        session: 数据库会话

    Returns:
        注册成功返回用户信息和 token
    """
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
        return AuthResponse(success=False, message=e.detail, error_code="REGISTRATION_FAILED")


@router.post("/login", response_model=AuthResponse)
async def login(
    login_data: UserLogin,
    session: Session = Depends(get_session)
) -> AuthResponse:
    """
    用户登录

    Args:
        login_data: 登录信息（账号、密码）
        session: 数据库会话

    Returns:
        登录成功返回用户信息和 token
    """
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
        return AuthResponse(success=False, message=e.detail, error_code="INVALID_CREDENTIALS")


@router.post("/logout", response_model=AuthResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> AuthResponse:
    """
    用户登出

    Args:
        current_user: 当前登录用户
        session: 数据库会话

    Returns:
        登出结果
    """
    await AuthService.logout_user(current_user, session)
    return AuthResponse(success=True, message="退出成功")


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> AuthResponse:
    """
    获取当前用户信息

    Args:
        current_user: 当前登录用户

    Returns:
        用户详细信息
    """
    # 根据是否使用默认 LLM 配置，决定返回的配置值
    llm_base_url = None if current_user.use_default_llm else current_user.llm_base_url
    llm_model = None if current_user.use_default_llm else current_user.llm_model
    last_login = current_user.last_login_time.isoformat() if current_user.last_login_time else None

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
            "llm_base_url": llm_base_url,
            "llm_model": llm_model,
            "created_at": current_user.created_at.isoformat(),
            "last_login_time": last_login
        }
    )


@router.put("/profile", response_model=AuthResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> AuthResponse:
    """
    更新用户资料

    Args:
        profile_data: 更新的资料（昵称、头像）
        current_user: 当前登录用户
        session: 数据库会话

    Returns:
        更新后的用户信息
    """
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
) -> AuthResponse:
    """
    修改密码

    Args:
        password_data: 密码信息（旧密码、新密码）
        current_user: 当前登录用户
        session: 数据库会话

    Returns:
        修改结果
    """
    from app.utils.auth import get_password_hash, verify_password

    if not verify_password(password_data.old_password, current_user.password_hash):
        return AuthResponse(success=False, message="原密码错误", error_code="INVALID_OLD_PASSWORD")

    current_user.password_hash = get_password_hash(password_data.new_password)
    session.add(current_user)
    session.commit()

    return AuthResponse(success=True, message="密码修改成功")


@router.get("/llm-config", response_model=AuthResponse)
async def get_llm_config(
    current_user: User = Depends(get_current_user)
) -> AuthResponse:
    """
    获取当前用户的 LLM 配置

    Args:
        current_user: 当前登录用户

    Returns:
        LLM 配置信息（不返回 API Key）
    """
    if current_user.use_default_llm:
        # 使用系统默认配置
        base_url = settings.DEFAULT_LLM_BASE_URL
        model = settings.DEFAULT_LLM_MODEL
        has_custom_key = False
    else:
        # 使用用户自定义配置
        base_url = current_user.llm_base_url
        model = current_user.llm_model
        has_custom_key = bool(current_user.llm_api_key)

    return AuthResponse(
        success=True,
        message="获取成功",
        data={
            "use_default_llm": current_user.use_default_llm,
            "llm_base_url": base_url,
            "llm_model": model,
            "has_custom_api_key": has_custom_key
        }
    )


@router.put("/llm-config", response_model=AuthResponse)
async def update_llm_config(
    config: LLMConfigUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> AuthResponse:
    """
    更新用户的 LLM 配置

    - use_default_llm=True: 使用系统默认配置
    - use_default_llm=False: 使用用户自定义配置，需提供 API Key

    Args:
        config: LLM 配置更新信息
        current_user: 当前登录用户
        session: 数据库会话

    Returns:
        更新后的 LLM 配置
    """
    current_user.use_default_llm = config.use_default_llm

    if config.use_default_llm:
        # 切换到默认配置，清空自定义配置
        current_user.llm_api_key = None
        current_user.llm_base_url = None
        current_user.llm_model = None
    else:
        # 使用自定义配置，API Key 必填
        if not config.llm_api_key:
            return AuthResponse(
                success=False,
                message="使用自定义 LLM 配置时，API Key 为必填项",
                error_code="MISSING_API_KEY"
            )
        current_user.llm_api_key = config.llm_api_key
        current_user.llm_base_url = config.llm_base_url or settings.DEFAULT_LLM_BASE_URL
        current_user.llm_model = config.llm_model or settings.DEFAULT_LLM_MODEL

    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return AuthResponse(
        success=True,
        message="LLM 配置更新成功",
        data={
            "use_default_llm": current_user.use_default_llm,
            "llm_base_url": current_user.llm_base_url or settings.DEFAULT_LLM_BASE_URL,
            "llm_model": current_user.llm_model or settings.DEFAULT_LLM_MODEL
        }
    )
