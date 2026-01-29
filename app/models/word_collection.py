from sqlmodel import SQLModel, Field, Column
from typing import Optional
from datetime import datetime
import uuid as uuid_pkg
from sqlalchemy import UUID, ForeignKey


class WordCollection(SQLModel, table=True):
    __tablename__ = "word_collections"

    id: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True)
    )
    user_id: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    name: str = Field(max_length=30, nullable=False)
    description: Optional[str] = Field(default=None, max_length=350)
    color: Optional[str] = Field(default=None, max_length=20)
    icon: Optional[str] = Field(default=None, max_length=50)
    word_count: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
