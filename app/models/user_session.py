from sqlmodel import SQLModel, Field, Column
from typing import Optional
from datetime import datetime
import uuid as uuid_pkg
from sqlalchemy import UUID, ForeignKey


class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"

    id: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True)
    )
    user_id: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    token: str = Field(max_length=500, nullable=False, index=True)
    refresh_token: Optional[str] = Field(default=None, max_length=500)
    device_info: Optional[str] = Field(default=None, max_length=255)
    ip_address: Optional[str] = Field(default=None, max_length=50)
    expires_at: datetime = Field(nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)