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

            # 构建最终队列：新词 + 穿插的待检验词
            final_queue = []
            pending_check_index = 0
            pending_check_total = len(pending_check_results)

            # 情况1：新词数量 < 3，直接在新词后插入所有待检验单词
            if len(new_words_sample) < 3:
                # 先添加所有新词
                for item, word in new_words_sample:
                    final_queue.append({
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

                # 再添加所有待检验单词
                for check_item, check_word in pending_check_results:
                    final_queue.append({
                        "item_id": str(check_item.id),
                        "word_id": str(check_word.id),
                        "word": check_word.word,
                        "chinese": check_word.content.get("chinese", ""),
                        "phonetic": check_word.content.get("phonetic", ""),
                        "part_of_speech": check_word.content.get("part_of_speech", ""),
                        "sentences": check_word.content.get("sentences", []),
                        "audio_url": f"/api/tts/{check_word.word}",
                        "is_recheck": True
                    })
            else:
                # 情况2：新词数量 >= 3
                # 情况2.1：待检验单词总数 < 3且 > 0，直接在前3个新词后全部插入
                if 0 < pending_check_total < 3:
                    for i, (item, word) in enumerate(new_words_sample):
                        final_queue.append({
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

                        # 在前3个新词后插入所有待检验单词
                        if i == 2 or i == len(new_words_sample) - 1:
                            for check_item, check_word in pending_check_results:
                                final_queue.append({
                                    "item_id": str(check_item.id),
                                    "word_id": str(check_word.id),
                                    "word": check_word.word,
                                    "chinese": check_word.content.get("chinese", ""),
                                    "phonetic": check_word.content.get("phonetic", ""),
                                    "part_of_speech": check_word.content.get("part_of_speech", ""),
                                    "sentences": check_word.content.get("sentences", []),
                                    "audio_url": f"/api/tts/{check_word.word}",
                                    "is_recheck": True
                                })
                            # 在第3个新词后插入完毕，继续处理剩余新词
                            if i == 2:
                                # 继续添加剩余的新词（不再插入待检验词）
                                for remaining_item, remaining_word in new_words_sample[3:]:
                                    final_queue.append({
                                        "item_id": str(remaining_item.id),
                                        "word_id": str(remaining_word.id),
                                        "word": remaining_word.word,
                                        "chinese": remaining_word.content.get("chinese", ""),
                                        "phonetic": remaining_word.content.get("phonetic", ""),
                                        "part_of_speech": remaining_word.content.get("part_of_speech", ""),
                                        "sentences": remaining_word.content.get("sentences", []),
                                        "audio_url": f"/api/tts/{remaining_word.word}",
                                        "is_recheck": False
                                    })
                                break
                else:
                    # 情况2.2：待检验单词 >= 3，每3个新词后插入3个待检验单词
                    for i, (item, word) in enumerate(new_words_sample):
                        final_queue.append({
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

                        # 每3个新词后插入3个待检验词
                        if (i + 1) % 3 == 0 or i == len(new_words_sample) - 1:
                            words_to_insert = min(3, pending_check_total - pending_check_index)
                            for j in range(words_to_insert):
                                if pending_check_index < pending_check_total:
                                    check_item, check_word = pending_check_results[pending_check_index]
                                    final_queue.append({
                                        "item_id": str(check_item.id),
                                        "word_id": str(check_word.id),
                                        "word": check_word.word,
                                        "chinese": check_word.content.get("chinese", ""),
                                        "phonetic": check_word.content.get("phonetic", ""),
                                        "part_of_speech": check_word.content.get("part_of_speech", ""),
                                        "sentences": check_word.content.get("sentences", []),
                                        "audio_url": f"/api/tts/{check_word.word}",
                                        "is_recheck": True
                                    })
                                    pending_check_index += 1

            words = final_queue

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
    async def submit_study(
        user_id: uuid_pkg.UUID,
        item_id: uuid_pkg.UUID,
        user_input: str,
        is_skip: bool,
        session: Session
    ) -> Dict[str, Any]:
        """提交学习结果"""
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
            item.fail_count += 1
            item.match_count = 0
            item.study_count += 1
            item.status = 0
            session.add(item)
            session.commit()
            return {
                "correct": False,
                "status_update": "已跳过",
                "correct_answer": correct_answer
            }

        # 检查答案
        is_correct = user_input.lower().strip() == correct_answer.lower().strip()

        # 无论对错，都增加学习次数
        item.study_count += 1

        if is_correct:
            item.review_count += 1
            item.last_review_time = datetime.utcnow()

            if item.status == 0 and item.match_count == 0:
                # 第一次匹配成功
                item.status = 1
                item.match_count = 1
                status_msg = "待检验"
                next_check = 3

            elif item.status == 1 and item.match_count == 1:
                # 第二次检验成功
                item.status = 2
                item.match_count = 0
                status_msg = "待复习"
                next_check = None

            elif item.status == 2:
                # 即时复习成功
                item.status = 3
                status_msg = "已背诵"
                next_check = None

            elif item.status == 3:
                # 完全复习成功
                item.status = 4
                status_msg = "背诵完成"
                next_check = None
            else:
                status_msg = "继续加油"
                next_check = None
        else:
            # 答错了
            item.fail_count += 1
            item.match_count = 0
            if item.status > 0:
                item.status = 0  # 重置为未背诵
            status_msg = "答错了，重新开始"
            next_check = None

        session.add(item)
        session.commit()

        return {
            "correct": is_correct,
            "status_update": status_msg,
            "next_check_after": next_check,
            "correct_answer": None if is_correct else correct_answer
        }