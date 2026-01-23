"""考试模块API"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app.database import get_session
from app.schemas.exam import (
    ExamGenerate, ExamResponse, ExamSubmit, ExamResult
)
from app.services.exam_service import ExamService
from app.utils.dependencies import get_current_user
from app.models import User
import uuid as uuid_pkg

router = APIRouter(prefix="/api/exam", tags=["考试"])


@router.post("/generate", response_model=ExamResponse)
async def generate_exam(
    exam_data: ExamGenerate,
    collection_id: uuid_pkg.UUID = Query(..., description="单词本ID"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """生成考试（使用用户配置的LLM）"""
    result = await ExamService.generate_exam(
        user=current_user,
        collection_id=collection_id,
        mode=exam_data.mode,
        count=exam_data.count,
        session=session
    )

    return ExamResponse(**result)


@router.post("/submit", response_model=ExamResult)
async def submit_exam(
    submit_data: ExamSubmit,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """提交考试"""
    result = await ExamService.submit_exam(
        exam_id=submit_data.exam_id,
        user_id=current_user.id,
        spelling_answers=submit_data.spelling_answers,
        translation_answers=submit_data.translation_answers,
        session=session
    )
    
    return ExamResult(**result)
