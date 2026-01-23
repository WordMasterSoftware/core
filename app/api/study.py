"""学习模块API"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app.database import get_session
from app.schemas.study import (
    StudyMode, StudySessionResponse, StudySubmit, StudySubmitResponse
)
from app.services.study_service import StudyService
from app.utils.dependencies import get_current_user
from app.models import User
import uuid as uuid_pkg

router = APIRouter(prefix="/api/study", tags=["学习"])


@router.get("/session", response_model=StudySessionResponse)
async def get_study_session(
    mode: StudyMode = Query(..., description="学习模式"),
    collection_id: uuid_pkg.UUID = Query(..., description="单词本ID"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """获取学习会话"""
    result = await StudyService.get_study_session(
        user_id=current_user.id,
        collection_id=collection_id,
        mode=mode,
        session=session
    )

    return StudySessionResponse(**result)


@router.post("/submit", response_model=StudySubmitResponse)
async def submit_study(
    submit_data: StudySubmit,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """提交学习结果"""
    result = await StudyService.submit_study(
        user_id=current_user.id,
        item_id=submit_data.item_id,
        user_input=submit_data.user_input,
        is_skip=submit_data.is_skip,
        session=session
    )

    return StudySubmitResponse(**result)
