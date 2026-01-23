from sqlmodel import SQLModel, Field, Column
from datetime import datetime
import uuid as uuid_pkg
from sqlalchemy import UUID

class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True)
    )
    user_id: uuid_pkg.UUID = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=100, nullable=False)
    content: str = Field(nullable=False)
    is_read: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
