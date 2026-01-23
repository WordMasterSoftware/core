"""学习条目管理API（重构版：适配单词本分类管理）"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app.database import get_session
from app.services.word_service import WordService
from app.utils.dependencies import get_current_user
from app.models import User
import uuid as uuid_pkg

router = APIRouter(prefix="/api/items", tags=["学习条目管理"])


@router.get("/{item_id}")
async def get_word_item(
    item_id: uuid_pkg.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """获取学习条目详情"""
    result = await WordService.get_word_item(
        item_id=item_id,
        user_id=current_user.id,
        session=session
    )
    return result


@router.delete("/{item_id}")
async def delete_word_item(
    item_id: uuid_pkg.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """删除学习条目（不删除wordbook中的单词）"""
    await WordService.delete_word_item(
        item_id=item_id,
        user_id=current_user.id,
        session=session
    )

    return {
        "success": True,
        "message": "学习条目已删除"
    }