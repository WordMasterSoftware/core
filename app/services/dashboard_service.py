from sqlmodel import Session, select, func
from datetime import datetime, date
from app.models import WordCollection, UserWordItem
import uuid as uuid_pkg

class DashboardService:
    @staticmethod
    async def get_stats(user_id: uuid_pkg.UUID, session: Session) -> dict:
        # 1. Total Collections
        total_collections = session.exec(
            select(func.count()).select_from(WordCollection).where(WordCollection.user_id == user_id)
        ).one()

        # 2. Total Words (Count of UserWordItem)
        # Use UserWordItem count for accuracy instead of relying on collection metadata
        total_words = session.exec(
            select(func.count()).select_from(UserWordItem).where(UserWordItem.user_id == user_id)
        ).one()

        # 3. To Review (Status = 2)
        to_review = session.exec(
            select(func.count()).select_from(UserWordItem).where(
                UserWordItem.user_id == user_id,
                UserWordItem.status == 2
            )
        ).one()

        # 4. Today Learned
        # Count items where last_review_time is today
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_learned = session.exec(
            select(func.count()).select_from(UserWordItem).where(
                UserWordItem.user_id == user_id,
                UserWordItem.last_review_time >= today_start
            )
        ).one()

        return {
            "total_words": total_words,
            "total_collections": total_collections,
            "today_learned": today_learned,
            "to_review": to_review
        }
