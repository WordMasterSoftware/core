"""考试模块API"""
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.schemas.exam import (
    ExamGenerateRequest, ExamGenerateResponse,
    ExamLoadRequest, ExamLoadResponse,
    ExamSubmitRequest, ExamSubmitResponse,
    ExamListResponse, ExamDetailResponse
)
from app.services.exam_service import ExamService
from app.utils.dependencies import get_current_user
from app.models import User
import uuid as uuid_pkg

router = APIRouter(prefix="/api/exam", tags=["考试"])


@router.post("/generate", response_model=ExamGenerateResponse)
async def generate_exam(
    exam_data: ExamGenerateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    生成考试（异步）
    - 创建考试记录
    - 后台触发生成任务
    """
    # 0. 检查是否满足生成条件 (至少10个单词)
    available_count = ExamService.check_review_availability(
        user_id=current_user.id,
        collection_id=exam_data.collection_id,
        mode=exam_data.mode,
        session=session
    )

    if available_count < 10:
        return ExamGenerateResponse(
            success=False,
            message=f"符合条件的单词不足10个（当前：{available_count}个），无法生成试卷。",
            exam_generation_status="failed"
        )

    # 1. 创建初始记录
    exam = ExamService.create_exam_record(
        user_id=current_user.id,
        collection_id=exam_data.collection_id,
        mode=exam_data.mode,
        count=exam_data.count,
        session=session
    )

    # 2. 添加后台任务
    background_tasks.add_task(
        ExamService.process_exam_generation,
        exam_id=exam.id,
        mode=exam_data.mode,
        target_count=exam_data.count,
        session=session
    )

    return ExamGenerateResponse(
        success=True,
        message="考试正在生成中，请稍后查看站内信或刷新考试列表",
        exam_generation_status="processing"
    )


@router.get("/info", response_model=ExamListResponse)
async def get_exam_list(
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """获取用户考试列表"""
    return ExamService.get_user_exams(
        user_id=current_user.id,
        page=page,
        size=size,
        session=session
    )


@router.get("/detail", response_model=ExamDetailResponse)
async def get_exam_detail(
    exam_id: uuid_pkg.UUID = Query(..., description="考试ID"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """获取考试详情（包含预览/加载）"""
    exam_detail = ExamService.get_exam_detail(exam_id, session)
    if not exam_detail:
        raise HTTPException(status_code=404, detail="Exam not found")

    # 简单的权限检查
    if exam_detail["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this exam")

    return ExamDetailResponse(**exam_detail)


@router.post("/submit", response_model=ExamSubmitResponse)
async def submit_exam(
    submit_data: ExamSubmitRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """提交考试"""
    if submit_data.user_id != current_user.id:
         # 虽然 Token 验证了身份，但请求体里的 ID 如果不一致也应该校验
         pass

    # 立即更新状态为阅卷中
    ExamService.mark_exam_as_grading(submit_data.exam_id, session)

    # 后台处理考试评分
    background_tasks.add_task(
        ExamService.submit_exam,
        exam_id=submit_data.exam_id,
        user_id=current_user.id,
        wrong_word_ids=submit_data.wrong_words,
        sentences_submission=submit_data.sentences,
        session=session
    )

    return ExamSubmitResponse(
        success=True,
        message="考试已提交，正在后台进行评分，结果将在几分钟后发送至站内信。"
    )


@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: uuid_pkg.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """删除考试"""
    try:
        success = ExamService.delete_exam(exam_id, current_user.id, session)
        if not success:
            raise HTTPException(status_code=404, detail="考试不存在")
        return {"success": True, "message": "考试已删除"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
