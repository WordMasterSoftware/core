from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import uuid as uuid_pkg

# --- Basic Section Models ---
class SpellingQuestion(BaseModel):
    word_id: uuid_pkg.UUID
    item_id: Optional[uuid_pkg.UUID] = None
    chinese: str
    english_answer: Optional[str] = None # Include answer for frontend validation

class TranslationQuestion(BaseModel):
    sentence_id: str
    # When loading, we send chinese sentence, user inputs english
    chinese: str
    words_involved: List[uuid_pkg.UUID]

# --- Request Models ---
class ExamGenerateRequest(BaseModel):
    # user_id comes from token usually, but existing API might ask for it explicitly?
    # Keeping it optional or as per design. Design says user_id is in body.
    user_id: Optional[uuid_pkg.UUID] = None
    collection_id: uuid_pkg.UUID
    mode: str # random, complete, immediate
    count: int = 20

class ExamLoadRequest(BaseModel):
    exam_id: uuid_pkg.UUID

class ExamSubmitRequest(BaseModel):
    exam_id: uuid_pkg.UUID
    user_id: Optional[uuid_pkg.UUID] = None
    collection_id: uuid_pkg.UUID
    wrong_words: List[uuid_pkg.UUID]
    # Sentence info submitted back for verification/record?
    # Design says: sentences: [{sentence_id, chinese, english, words_involved}]
    # But usually we submit answers. The design implies we submit the *result* or the *answer*?
    # "翻译使用大模型评判 用户提交答案后 由系统后端发送一条站内信"
    # The "submit" API parameters in design:
    # sentences: [{sentence_id, chinese, english, words_involved}] -> This looks like the *question* info + user's answer?
    # Let's stick to the design JSON structure.
    sentences: List[Dict]

# --- Response Models ---

class ExamGenerateResponse(BaseModel):
    success: bool
    message: str
    exam_generation_status: str

class ExamLoadResponse(BaseModel):
    exam_id: uuid_pkg.UUID
    spelling_section: List[SpellingQuestion]
    translation_section: List[TranslationQuestion]

class ExamSubmitResponse(BaseModel):
    success: bool
    message: str

# --- List/Info Models ---

class ExamInfo(BaseModel):
    exam_id: uuid_pkg.UUID
    user_id: uuid_pkg.UUID
    collection_name: Optional[str] = None
    total_words: int
    spelling_words_count: int
    translation_sentences_count: int
    exam_status: str
    mode: str
    created_at: datetime
    completed_at: Optional[datetime] = None

class ExamListResponse(BaseModel):
    exams: List[ExamInfo]
    pagination: Dict[str, int]

class ExamDetailResponse(BaseModel):
    exam_id: uuid_pkg.UUID
    user_id: uuid_pkg.UUID
    collection_id: uuid_pkg.UUID
    collection_name: Optional[str] = None
    exam_status: str
    total_words: int
    spelling_words_count: int
    translation_sentences_count: int
    estimated_duration_minutes: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    spelling_section: List[SpellingQuestion]
    translation_section: List[TranslationQuestion]
