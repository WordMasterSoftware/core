"""学习服务（重构版：适配单词本分类管理）"""
from sqlmodel import Session, select
from app.models import UserWordItem, WordBook, WordCollection
from app.schemas.study import StudyMode
from typing import List, Dict, Any
import uuid as uuid_pkg
from datetime import datetime
import random


class StudyService:
    @staticmethod
    async def get_study_session(
        user_id: uuid_pkg.UUID,
        collection_id: uuid_pkg.UUID,  # 新增：指定单词本
        mode: StudyMode,
        session: Session
    ) -> Dict[str, Any]:
        """获取学习会话（从指定单词本中）- 包含待检验单词自动插入逻辑"""

        # 验证单词本存在且属于该用户
        collection_statement = select(WordCollection).where(
            WordCollection.id == collection_id,
            WordCollection.user_id == user_id
        )
        collection = session.exec(collection_statement).first()
        if not collection:
            return {
                "mode": mode,
                "words": [],
                "total_count": 0,
                "error": "单词本不存在"
            }

        if mode == StudyMode.NEW:
            # 新词背诵：状态为0的新词
            new_words_statement = select(UserWordItem, WordBook).join(
                WordBook, UserWordItem.word_id == WordBook.id
            ).where(
                UserWordItem.collection_id == collection_id,
                UserWordItem.user_id == user_id,
                UserWordItem.status == 0
            )
            new_words_results = session.exec(new_words_statement).all()

            # 待检验单词：status=1
            pending_check_statement = select(UserWordItem, WordBook).join(
                WordBook, UserWordItem.word_id == WordBook.id
            ).where(
                UserWordItem.collection_id == collection_id,
                UserWordItem.user_id == user_id,
                UserWordItem.status == 1
            )
            pending_check_results = session.exec(pending_check_statement).all()

            # 随机抽取新词
            new_words_sample = random.sample(new_words_results, min(20, len(new_words_results)))

            # 使用 helper method 混合新词和待检验词
            words = StudyService._mix_new_and_pending_words(new_words_sample, pending_check_results)

        elif mode == StudyMode.REVIEW:
            # 即时复习：状态为2，随机50个
            statement = select(UserWordItem, WordBook).join(
                WordBook, UserWordItem.word_id == WordBook.id
            ).where(
                UserWordItem.collection_id == collection_id,
                UserWordItem.user_id == user_id,
                UserWordItem.status == 2
            )
            results = session.exec(statement).all()
            results = random.sample(results, min(50, len(results)))

            words = []
            for item, word in results:
                words.append({
                    "item_id": str(item.id),
                    "word_id": str(word.id),
                    "word": word.word,
                    "chinese": word.content.get("chinese", ""),
                    "phonetic": word.content.get("phonetic", ""),
                    "part_of_speech": word.content.get("part_of_speech", ""),
                    "sentences": word.content.get("sentences", []),
                    "audio_url": f"/api/tts/{word.word}",
                    "is_recheck": False
                })

        elif mode == StudyMode.RANDOM:
            # 随机复习：状态为3，随机20个
            statement = select(UserWordItem, WordBook).join(
                WordBook, UserWordItem.word_id == WordBook.id
            ).where(
                UserWordItem.collection_id == collection_id,
                UserWordItem.user_id == user_id,
                UserWordItem.status == 3
            )
            results = session.exec(statement).all()
            results = random.sample(results, min(20, len(results)))

            words = []
            for item, word in results:
                words.append({
                    "item_id": str(item.id),
                    "word_id": str(word.id),
                    "word": word.word,
                    "chinese": word.content.get("chinese", ""),
                    "phonetic": word.content.get("phonetic", ""),
                    "part_of_speech": word.content.get("part_of_speech", ""),
                    "sentences": word.content.get("sentences", []),
                    "audio_url": f"/api/tts/{word.word}",
                    "is_recheck": False
                })

        elif mode == StudyMode.FINAL:
            # 完全复习：状态为3，随机100个
            statement = select(UserWordItem, WordBook).join(
                WordBook, UserWordItem.word_id == WordBook.id
            ).where(
                UserWordItem.collection_id == collection_id,
                UserWordItem.user_id == user_id,
                UserWordItem.status == 3
            )
            results = session.exec(statement).all()
            results = random.sample(results, min(100, len(results)))

            words = []
            for item, word in results:
                words.append({
                    "item_id": str(item.id),
                    "word_id": str(word.id),
                    "word": word.word,
                    "chinese": word.content.get("chinese", ""),
                    "phonetic": word.content.get("phonetic", ""),
                    "part_of_speech": word.content.get("part_of_speech", ""),
                    "sentences": word.content.get("sentences", []),
                    "audio_url": f"/api/tts/{word.word}",
                    "is_recheck": False
                })

        return {
            "mode": mode,
            "collection_id": str(collection_id),
            "collection_name": collection.name,
            "words": words,
            "total_count": len(words)
        }

    @staticmethod
    def _format_word_for_queue(item, word, is_recheck: bool):
        return {
            "item_id": str(item.id),
            "word_id": str(word.id),
            "word": word.word,
            "chinese": word.content.get("chinese", ""),
            "phonetic": word.content.get("phonetic", ""),
            "part_of_speech": word.content.get("part_of_speech", ""),
            "sentences": word.content.get("sentences", []),
            "audio_url": f"/api/tts/{word.word}",
            "is_recheck": is_recheck
        }

    @staticmethod
    def _mix_new_and_pending_words(new_words_sample, pending_check_results):
        """
        Helper to mix new words (Status 0) and pending check words (Status 1).
        Logic:
        1. If new words < 3: Append all pending words after new words.
        2. If pending words < 3: Insert all pending words after the 3rd new word (or end).
        3. Else (Many pending): Insert 3 pending words after every 3 new words.
        """
        final_queue = []
        pending_check_index = 0
        pending_check_total = len(pending_check_results)

        # Scenario 1: Few new words
        if len(new_words_sample) < 3:
            for item, word in new_words_sample:
                final_queue.append(StudyService._format_word_for_queue(item, word, False))
            for item, word in pending_check_results:
                final_queue.append(StudyService._format_word_for_queue(item, word, True))
            return final_queue

        # Scenario 2: Many new words
        for i, (item, word) in enumerate(new_words_sample):
            final_queue.append(StudyService._format_word_for_queue(item, word, False))

            # Check insertion point (After 3rd word, 6th word... or end)
            should_insert = (i + 1) % 3 == 0 or i == len(new_words_sample) - 1

            if should_insert:
                # Scenario 2.1: Few pending words (<3)
                if 0 < pending_check_total < 3:
                     # Insert all at the first opportunity (i==2 or end)
                     if i == 2 or (i < 2 and i == len(new_words_sample) - 1):
                         # If we haven't inserted them yet (implied by logic flow control, but here we can just check index)
                         if pending_check_index == 0:
                             for check_item, check_word in pending_check_results:
                                 final_queue.append(StudyService._format_word_for_queue(check_item, check_word, True))
                             pending_check_index = pending_check_total # All done

                # Scenario 2.2: Many pending words (>=3)
                else:
                    words_to_insert = min(3, pending_check_total - pending_check_index)
                    for _ in range(words_to_insert):
                        check_item, check_word = pending_check_results[pending_check_index]
                        final_queue.append(StudyService._format_word_for_queue(check_item, check_word, True))
                        pending_check_index += 1

        return final_queue

    @staticmethod
    async def submit_study(
        user_id: uuid_pkg.UUID,
        item_id: uuid_pkg.UUID,
        user_input: str,
        is_skip: bool,
        session: Session
    ) -> Dict[str, Any]:
        """提交学习结果"""
        from app.services.progress_service import ProgressService

        # 获取学习条目和单词
        statement = select(UserWordItem, WordBook).join(
            WordBook, UserWordItem.word_id == WordBook.id
        ).where(
            UserWordItem.id == item_id,
            UserWordItem.user_id == user_id
        )
        result = session.exec(statement).first()

        if not result:
            return {"correct": False, "status_update": "未找到该学习条目"}

        item, word = result
        correct_answer = word.word

        # 跳过
        if is_skip:
            ProgressService.reset_to_new(item, session, is_skip=True)
            return {
                "correct": False,
                "status_update": "已跳过",
                "correct_answer": correct_answer
            }

        # 检查答案
        is_correct = user_input.lower().strip() == correct_answer.lower().strip()

        # 更新进度
        status_msg = ProgressService.update_study_progress(item, is_correct, session)

        return {
            "correct": is_correct,
            "status_update": status_msg,
            "next_check_after": None, # Removed hardcoded 3, frontend might handle flow
            "correct_answer": None if is_correct else correct_answer
        }