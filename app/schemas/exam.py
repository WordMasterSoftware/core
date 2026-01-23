from pydantic import BaseModel
from typing import List, Dict, Optional
import uuid as uuid_pkg


class SpellingQuestion(BaseModel):
    word_id: uuid_pkg.UUID
    chinese: str


class TranslationQuestion(BaseModel):
    sentence_id: str
    english: str
    words_involved: List[str]


class ExamGenerate(BaseModel):
    user_id: uuid_pkg.UUID
    mode: str
    count: int = 50


class ExamResponse(BaseModel):
    exam_id: str
    spelling_section: List[SpellingQuestion]
    translation_section: List[TranslationQuestion]


class ExamSubmit(BaseModel):
    exam_id: str
    user_id: uuid_pkg.UUID
    spelling_answers: Dict[str, str]
    translation_answers: Dict[str, str]


class TranslationResult(BaseModel):
    sentence_id: str
    correct: bool
    feedback: str


class ExamResult(BaseModel):
    spelling_score: int
    translation_results: List[TranslationResult]
    failed_words: List[str]
    pass_exam: bool
