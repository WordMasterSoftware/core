from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, ARRAY, Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class Exam(SQLModel, table=True):
    __tablename__ = "exams"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    collection_id: UUID = Field(foreign_key="word_collections.id")
    mode: str = Field(default="immediate") # immediate, random, complete
    exam_status: str = Field(default="pending") # pending, generated, grading, completed, failed
    total_words: int
    spelling_words_count: int
    translation_sentences_count: int
    generation_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

class ExamSpellingSection(SQLModel, table=True):
    __tablename__ = "exam_spelling_sections"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    exam_id: UUID = Field(foreign_key="exams.id")
    word_id: UUID = Field(foreign_key="wordbook.id")
    item_id: UUID = Field(foreign_key="user_word_items.id")
    chinese_meaning: str
    english_answer: str
    created_at: datetime = Field(default_factory=datetime.now)

class ExamTranslationSection(SQLModel, table=True):
    __tablename__ = "exam_translation_sections"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    exam_id: UUID = Field(foreign_key="exams.id")
    sentence_id: str
    chinese_sentence: str
    # SQLModel doesn't support ARRAY directly in all versions, using SA Column
    words_involved: List[UUID] = Field(sa_column=Column(ARRAY(PG_UUID)))
    created_at: datetime = Field(default_factory=datetime.now)
