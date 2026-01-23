from pydantic import BaseModel
from typing import List, Optional
import uuid as uuid_pkg
from enum import Enum


class StudyMode(str, Enum):
    NEW = "new"
    REVIEW = "review"
    RANDOM = "random"
    FINAL = "final"


class StudyWord(BaseModel):
    item_id: uuid_pkg.UUID
    word_id: uuid_pkg.UUID
    word: str
    chinese: str
    phonetic: str
    part_of_speech: str
    sentences: List[str]
    audio_url: str
    is_recheck: bool = False  # 是否为检验单词


class StudySessionResponse(BaseModel):
    mode: StudyMode
    words: List[StudyWord]
    total_count: int


class StudySubmit(BaseModel):
    item_id: uuid_pkg.UUID
    user_input: str
    is_skip: bool = False


class StudySubmitResponse(BaseModel):
    correct: bool
    status_update: str
    next_check_after: Optional[int] = None
    correct_answer: Optional[str] = None
