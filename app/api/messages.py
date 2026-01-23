from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, desc
from app.database import get_session
from app.models.user import User
from app.models.message import Message
from app.utils.dependencies import get_current_user
import uuid

router = APIRouter(prefix="/api/messages", tags=["消息"])

@router.get("/", response_model=dict)
def get_messages(
    page: int = 1,
    size: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    获取消息列表
    """
    query = select(Message).where(Message.user_id == current_user.id)

    if unread_only:
        query = query.where(Message.is_read == False)

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()

    # 获取分页数据，按时间倒序
    query = query.order_by(desc(Message.created_at)).offset((page - 1) * size).limit(size)
    messages = session.exec(query).all()

    # 获取未读总数
    unread_count_query = select(func.count()).where(Message.user_id == current_user.id, Message.is_read == False)
    unread_count = session.exec(unread_count_query).one()

    return {
        "items": messages,
        "total": total,
        "page": page,
        "size": size,
        "unread_count": unread_count
    }

@router.put("/{message_id}/read")
def mark_as_read(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    标记单个消息为已读
    """
    message = session.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")

    if message.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无法操作他人消息")

    message.is_read = True
    session.add(message)
    session.commit()
    session.refresh(message)
    return message

@router.put("/read-all")
def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    全部标记为已读
    """
    statement = select(Message).where(Message.user_id == current_user.id, Message.is_read == False)
    messages = session.exec(statement).all()

    for message in messages:
        message.is_read = True
        session.add(message)

    session.commit()
    return {"count": len(messages), "status": "success"}

@router.delete("/{message_id}")
def delete_message(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    删除消息
    """
    message = session.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")

    if message.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无法操作他人消息")

    session.delete(message)
    session.commit()
    return {"status": "success"}
