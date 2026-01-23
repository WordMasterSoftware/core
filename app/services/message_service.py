from sqlmodel import Session
from app.models.message import Message
import uuid

class MessageService:
    @staticmethod
    def create_message(session: Session, user_id: uuid.UUID, title: str, content: str) -> Message:
        """
        创建一个新消息（供内部服务调用）
        """
        message = Message(
            user_id=user_id,
            title=title,
            content=content
        )
        session.add(message)
        session.commit()
        session.refresh(message)
        return message
