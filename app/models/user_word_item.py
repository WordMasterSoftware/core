from sqlmodel import SQLModel, Field, Column
from typing import Optional
from datetime import datetime
import uuid as uuid_pkg
from sqlalchemy import UUID, ForeignKey, Integer, CheckConstraint


class UserWordItem(SQLModel, table=True):
    __tablename__ = "user_word_items"

    # 四项 ID 设计
    id: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True)
    )
    collection_id: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("word_collections.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    user_id: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    word_id: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("wordbook.id", ondelete="RESTRICT"), nullable=False, index=True)
    )

    # 学习进度字段
    status: int = Field(default=0, index=True)
    review_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    match_count: int = Field(default=0)
    study_count: int = Field(default=0)
    last_review_time: Optional[datetime] = Field(default=None, index=True)
    next_review_due: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("status IN (0, 1, 2, 3, 4)", name="check_status"),
    )
