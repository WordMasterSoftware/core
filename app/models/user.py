from sqlmodel import SQLModel, Field, Column, String
from typing import Optional
from datetime import datetime
import uuid as uuid_pkg
from sqlalchemy import UUID


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True)
    )
    username: str = Field(max_length=50, unique=True, index=True, nullable=False)
    email: str = Field(max_length=100, unique=True, index=True, nullable=False)
    password_hash: str = Field(max_length=255, nullable=False)
    nickname: Optional[str] = Field(default=None, max_length=50)
    avatar_url: Optional[str] = Field(default=None, max_length=255)
    
    # LLM 配置字段
    use_default_llm: bool = Field(default=True, nullable=False)
    llm_api_key: Optional[str] = Field(default=None, max_length=500)
    llm_base_url: Optional[str] = Field(default=None, max_length=255)
    llm_model: Optional[str] = Field(default=None, max_length=100)
    
    last_login_time: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
