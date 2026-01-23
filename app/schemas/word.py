from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid as uuid_pkg
from datetime import datetime


class WordContent(BaseModel):
    chinese: str
    phonetic: str
    part_of_speech: str
    sentences: List[str]


class WordImport(BaseModel):
    words: List[str] = Field(..., min_length=1)


class WordImportResponse(BaseModel):
    success: bool
    imported: int
    duplicates: int
    task_id: Optional[str] = None


class WordResponse(BaseModel):
    id: uuid_pkg.UUID
    word: str
    content: Dict[str, Any]
    status: Optional[int] = None
    created_at: datetime


class WordListResponse(BaseModel):
    total: int
    words: List[WordResponse]
    page: int
    page_size: int
