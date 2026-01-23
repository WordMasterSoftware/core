from sqlmodel import SQLModel, Field, Column
from typing import Dict, Any
from datetime import datetime
import uuid as uuid_pkg
from sqlalchemy import UUID
from sqlalchemy.dialects.postgresql import JSONB


class WordBook(SQLModel, table=True):
    __tablename__ = "wordbook"

    id: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True)
    )
    word: str = Field(max_length=100, unique=True, index=True, nullable=False)
    content: Dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=False)
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)