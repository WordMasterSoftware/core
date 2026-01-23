from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
import uuid as uuid_pkg
from datetime import datetime
import re


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=20)
    nickname: Optional[str] = Field(None, max_length=50)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not re.search(r'[a-zA-Z]', v) or not re.search(r'\d', v):
            raise ValueError('密码必须包含至少一个字母和一个数字')
        return v


class UserLogin(BaseModel):
    account: str = Field(..., description="用户名或邮箱")
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class UserResponse(BaseModel):
    user_id: uuid_pkg.UUID
    username: str
    email: str
    nickname: Optional[str]
    avatar_url: Optional[str]
    use_default_llm: bool
    llm_base_url: Optional[str]
    llm_model: Optional[str]
    created_at: datetime
    last_login_time: Optional[datetime]


class AuthResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    error_code: Optional[str] = None


class ProfileUpdate(BaseModel):
    nickname: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=255)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=20)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        if not re.search(r'[a-zA-Z]', v) or not re.search(r'\d', v):
            raise ValueError('密码必须包含至少一个字母和一个数字')
        return v


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# LLM 配置相关
class LLMConfigUpdate(BaseModel):
    """用户LLM配置更新"""
    use_default_llm: bool = Field(..., description="是否使用系统默认LLM配置")
    llm_api_key: Optional[str] = Field(None, max_length=500, description="LLM API Key (use_default_llm=False时必填)")
    llm_base_url: Optional[str] = Field(None, max_length=255, description="LLM API Endpoint")
    llm_model: Optional[str] = Field(None, max_length=100, description="LLM Model")

    @field_validator('llm_api_key')
    @classmethod
    def validate_api_key(cls, v, info):
        # 如果不使用默认配置，API Key 必填
        if not info.data.get('use_default_llm') and not v:
            raise ValueError('使用自定义LLM配置时，API Key为必填项')
        return v


class LLMConfigResponse(BaseModel):
    """用户LLM配置响应"""
    use_default_llm: bool
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    # 注意：不返回 API Key（安全考虑）
