"""认证服务"""
from sqlmodel import Session, select
from app.models import User, UserSession
from app.schemas.auth import UserRegister, UserLogin
from app.utils.auth import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    hash_token
)
from datetime import datetime, timedelta
from app.config import settings
from fastapi import HTTPException, status
from typing import Tuple, Optional
import uuid as uuid_pkg


class AuthService:
    @staticmethod
    async def register_user(
        user_data: UserRegister, 
        session: Session
    ) -> Tuple[User, str, str]:
        """注册用户"""
        # 检查用户名是否存在
        statement = select(User).where(User.username == user_data.username)
        existing_user = session.exec(statement).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 检查邮箱是否存在
        email_lower = user_data.email.lower()
        statement = select(User).where(User.email == email_lower)
        existing_email = session.exec(statement).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在"
            )

        # 创建用户
        user = User(
            username=user_data.username,
            email=email_lower,
            password_hash=get_password_hash(user_data.password),
            nickname=user_data.nickname or user_data.username,
            last_login_time=datetime.utcnow()
        )
        
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # 创建令牌
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})
        
        # 创建会话
        user_session = UserSession(
            user_id=user.id,
            token=hash_token(access_token),
            refresh_token=hash_token(refresh_token),
            expires_at=datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        session.add(user_session)
        session.commit()
        
        return user, access_token, refresh_token
    
    @staticmethod
    async def login_user(
        login_data: UserLogin, 
        session: Session
    ) -> Tuple[User, str, str]:
        """用户登录"""
        # 查找用户（通过用户名或邮箱）
        statement = select(User).where(
            (User.username == login_data.account) | (User.email == login_data.account.lower())
        )
        user = session.exec(statement).first()
        
        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 更新最后登录时间
        user.last_login_time = datetime.utcnow()
        session.add(user)
        session.commit()
        
        # 创建令牌
        expires_delta = None
        if login_data.remember_me:
            expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        access_token = create_access_token({"sub": str(user.id)}, expires_delta)
        refresh_token = create_refresh_token({"sub": str(user.id)})
        
        # 创建会话
        user_session = UserSession(
            user_id=user.id,
            token=hash_token(access_token),
            refresh_token=hash_token(refresh_token),
            expires_at=datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        )
        session.add(user_session)
        session.commit()
        
        return user, access_token, refresh_token
    
    @staticmethod
    async def logout_user(user: User, session: Session):
        """用户登出"""
        # 删除所有会话
        statement = select(UserSession).where(UserSession.user_id == user.id)
        sessions = session.exec(statement).all()
        for user_session in sessions:
            session.delete(user_session)
        session.commit()
