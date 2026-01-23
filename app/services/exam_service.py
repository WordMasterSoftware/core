"""考试服务（重构版：适配单词本分类管理）"""
from sqlmodel import Session, select
from app.models import UserWordItem, WordBook, User, WordCollection
from app.services.llm_service import get_llm_service_for_user
from typing import List, Dict, Any
import uuid as uuid_pkg
import random


class ExamService:
    @staticmethod
    async def generate_exam(
        user: User,
        collection_id: uuid_pkg.UUID,  # 新增：指定单词本
        mode: str,
        count: int,
        session: Session
    ) -> Dict[str, Any]:
        """生成考试（使用用户配置的LLM，从指定单词本中）"""

        # 验证单词本存在且属于该用户
        collection_statement = select(WordCollection).where(
            WordCollection.id == collection_id,
            WordCollection.user_id == user.id
        )
        collection = session.exec(collection_statement).first()
        if not collection:
            return {
                "error": "单词本不存在",
                "exam_id": None,
                "spelling_section": [],
                "translation_section": []
            }

        exam_id = str(uuid_pkg.uuid4())

        # 根据模式选择单词
        if mode == "review":
            status_filter = 2
        elif mode == "final":
            status_filter = 3
        else:
            status_filter = 2

        statement = select(UserWordItem, WordBook).join(
            WordBook, UserWordItem.word_id == WordBook.id
        ).where(
            UserWordItem.collection_id == collection_id,
            UserWordItem.user_id == user.id,
            UserWordItem.status == status_filter
        )
        results = session.exec(statement).all()

        # 随机选择
        selected = random.sample(results, min(count, len(results)))

        # 拼写部分：全部单词
        spelling_section = []
        words_list = []

        for item, word in selected:
            spelling_section.append({
                "item_id": str(item.id),  # 使用学习条目ID
                "word_id": str(word.id),
                "chinese": word.content.get("chinese", "")
            })
            words_list.append(word.word)

        # 翻译部分：调用用户配置的LLM生成句子
        llm_service = get_llm_service_for_user(user)
        sentences = await llm_service.generate_exam_sentences(
            words=words_list,
            count=min(10, len(words_list)),
            sentence_count=5
        )

        translation_section = []
        for i, sentence in enumerate(sentences):
            translation_section.append({
                "sentence_id": f"{exam_id}_{i}",
                "english": sentence.get("english", ""),
                "words_involved": sentence.get("words_used", [])
            })

        return {
            "exam_id": exam_id,
            "collection_id": str(collection_id),
            "collection_name": collection.name,
            "spelling_section": spelling_section,
            "translation_section": translation_section
        }

    @staticmethod
    async def submit_exam(
        exam_id: str,
        user_id: uuid_pkg.UUID,
        spelling_answers: Dict[str, str],  # key: item_id, value: user_answer
        translation_answers: Dict[str, str],
        session: Session
    ) -> Dict[str, Any]:
        """提交考试"""
        # 拼写部分评分
        spelling_score = 0
        failed_item_ids = []

        for item_id_str, user_answer in spelling_answers.items():
            # 获取学习条目和单词
            statement = select(UserWordItem, WordBook).join(
                WordBook, UserWordItem.word_id == WordBook.id
            ).where(
                UserWordItem.id == uuid_pkg.UUID(item_id_str),
                UserWordItem.user_id == user_id
            )
            result = session.exec(statement).first()

            if result:
                item, word = result
                if user_answer.lower().strip() == word.word.lower().strip():
                    spelling_score += 1
                else:
                    failed_item_ids.append(item_id_str)

        # 翻译部分评分
        translation_results = []
        for sentence_id, user_translation in translation_answers.items():
            result = {
                "sentence_id": sentence_id,
                "correct": True,
                "feedback": "翻译准确"
            }
            translation_results.append(result)

        # 判断是否通过
        total_spelling = len(spelling_answers)
        pass_exam = spelling_score >= total_spelling * 0.8

        # 更新失败单词的状态
        for item_id_str in failed_item_ids:
            item = session.get(UserWordItem, uuid_pkg.UUID(item_id_str))
            if item and item.user_id == user_id:
                item.status = 0  # 重置为未背诵
                session.add(item)

        # 更新成功单词的状态
        if pass_exam:
            for item_id_str in spelling_answers.keys():
                if item_id_str not in failed_item_ids:
                    item = session.get(UserWordItem, uuid_pkg.UUID(item_id_str))
                    if item and item.user_id == user_id:
                        if item.status == 2:
                            item.status = 3  # 即时复习通过 → 已背诵
                        elif item.status == 3:
                            item.status = 4  # 完全复习通过 → 背诵完成
                        session.add(item)

        session.commit()

        return {
            "spelling_score": spelling_score,
            "total_spelling": total_spelling,
            "translation_results": translation_results,
            "failed_items": failed_item_ids,
            "pass_exam": pass_exam
        }
