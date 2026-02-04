from datetime import datetime
from sqlmodel import Session
from app.models import UserWordItem

class ProgressService:
    """
    Centralized service for managing word learning progress and status transitions.
    Status Definitions:
    0: New (Not memorized / Failed)
    1: Pending Check (Matched once)
    2: Pending Review (Passed double check, waiting for review exam)
    3: Review Passed (Passed immediate review)
    4: Mastered (Passed final review)
    """

    @staticmethod
    def reset_to_new(item: UserWordItem, session: Session, is_skip: bool = False):
        """Reset word status to 0 (New) due to failure or skip."""
        if is_skip:
            item.study_count += 1
            # Skip counts as a fail for status reset purposes but we track it

        item.fail_count += 1
        item.match_count = 0
        if item.status > 0:
            item.status = 0

        session.add(item)
        session.commit()

    @staticmethod
    def update_study_progress(item: UserWordItem, is_correct: bool, session: Session) -> str:
        """
        Handle progress update for single word study (Study Mode).
        Returns status message.
        """
        item.study_count += 1

        if not is_correct:
            ProgressService.reset_to_new(item, session)
            return "答错了，重新开始"

        # Correct Answer Logic
        item.review_count += 1
        item.last_review_time = datetime.utcnow()
        status_msg = "继续加油"

        if item.status == 0:
            if item.match_count == 0:
                # 0 -> 1
                item.status = 1
                item.match_count = 1
                status_msg = "待检验"
            # If match_count was > 0 for some reason, keep it 1 or move?
            # Logic from original StudyService: status==0 and match==0 -> status=1

        elif item.status == 1:
            if item.match_count == 1:
                # 1 -> 2
                item.status = 2
                item.match_count = 0
                status_msg = "待复习"

        elif item.status == 2:
            # Study mode usually doesn't handle 2->3 (that's Exam), but if user studies "Pending Review" words directly
            item.status = 3
            status_msg = "已背诵"

        elif item.status == 3:
            item.status = 4
            status_msg = "背诵完成"

        session.add(item)
        session.commit()
        return status_msg

    @staticmethod
    def update_exam_success(item: UserWordItem, mode: str, session: Session):
        """
        Handle progress update for Exam success.
        """
        item.review_count += 1
        item.last_review_time = datetime.utcnow()

        if mode in ['immediate', 'random']:
            # Immediate/Random: Status 2 -> 3
            if item.status == 2:
                item.status = 3
        elif mode == 'complete':
            # Complete: Status 3 -> 4
            if item.status == 3:
                item.status = 4

        session.add(item)
        session.commit()
