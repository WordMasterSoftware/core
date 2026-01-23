"""单词管理服务（重构版：支持单词本分类管理）"""
from sqlmodel import Session, select
from app.models import WordBook, UserWordItem, User, WordCollection
from app.services.llm_service import get_llm_service_for_user
from app.services.message_service import MessageService
from app.database import engine
from typing import List, Dict, Any
import uuid as uuid_pkg
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class WordService:
    @staticmethod
    async def import_words_background_task(
        user_id: uuid_pkg.UUID,
        collection_id: uuid_pkg.UUID,
        words: List[str]
    ):
        """
        后台导入任务：处理单词导入、调用LLM、发送通知
        """
        logger.info(f"Starting background import task for user {user_id}, collection {collection_id}")

        # 创建新的数据库会话，因为后台任务在响应返回后执行，不能依赖请求范围的session
        with Session(engine) as session:
            try:
                # 获取用户信息（用于LLM配置）
                user = session.get(User, user_id)
                if not user:
                    logger.error(f"User {user_id} not found during background import")
                    return

                # 获取单词本信息
                collection = session.get(WordCollection, collection_id)
                if not collection:
                    logger.error(f"Collection {collection_id} not found during background import")
                    # 尝试发送失败通知
                    MessageService.create_message(
                        session=session,
                        user_id=user_id,
                        title="单词导入失败",
                        content="目标单词本不存在或已被删除。"
                    )
                    return

                # 复用原有的导入逻辑
                # 注意：import_words_to_collection 是 async 方法，需要 await
                result = await WordService.import_words_to_collection(
                    user=user,
                    collection_id=collection_id,
                    words=words,
                    session=session
                )

                # 构建通知内容
                title = "单词导入完成"
                content = (
                    f"恭喜！单词本 {collection.name} 中的 {result['total']} 个单词已经被成功处理。\n"
                    f"实际导入 {result['imported']} 个单词，"
                    f"有效去重 {result['duplicates']} 个，"
                    f"复用已有单词 {result['reused']} 个，"
                    f"调用 LLM 生成了 {result['llm_generated']} 个。\n"
                    f"已尽全力为您节省 TOKEN"
                )

                # 发送成功通知
                MessageService.create_message(
                    session=session,
                    user_id=user_id,
                    title=title,
                    content=content
                )
                logger.info(f"Background import task completed for user {user_id}")

            except Exception as e:
                logger.error(f"Error in background import task: {e}", exc_info=True)
                # 尝试发送错误通知
                try:
                    MessageService.create_message(
                        session=session,
                        user_id=user_id,
                        title="单词导入失败",
                        content=f"处理过程中发生错误: {str(e)}"
                    )
                except Exception as inner_e:
                    logger.error(f"Failed to send error notification: {inner_e}")

    @staticmethod
    async def import_words_to_collection(
        user: User,
        collection_id: uuid_pkg.UUID,
        words: List[str],
        session: Session
    ) -> Dict[str, Any]:
        """
        导入单词到指定单词本（优化版）

        优化策略：
        1. 请求去重：对传入的单词列表先去重
        2. 用户单词本去重：检查该用户在该单词本中是否已有这些单词
        3. 复用其他用户的单词：检查数据库中是否已有相同单词，直接复用避免调用LLM
        4. 仅对新单词调用LLM：只对数据库中不存在的单词调用LLM生成翻译
        5. 结果去重：确保最终结果不重复
        """
        # 验证单词本存在且属于该用户
        # 注意：在后台任务调用时，已经在外部检查了，但保留此处检查无害
        collection_statement = select(WordCollection).where(
            WordCollection.id == collection_id,
            WordCollection.user_id == user.id
        )
        collection = session.exec(collection_statement).first()
        if not collection:
            raise HTTPException(status_code=404, detail="单词本不存在")

        # 使用用户配置的LLM服务
        llm_service = get_llm_service_for_user(user)

        # 第一步：对请求中的单词去重并标准化
        unique_words = list(set([word.lower().strip() for word in words if word.strip()]))

        if not unique_words:
            return {
                "imported": 0,
                "duplicates": 0,
                "reused": 0,
                "llm_generated": 0,
                "total": 0,
                "failed": 0
            }

        # 第二步：检查该单词本中已有的单词（避免重复导入）
        collection_items_statement = select(UserWordItem, WordBook).join(
            WordBook, UserWordItem.word_id == WordBook.id
        ).where(
            UserWordItem.collection_id == collection_id,
            WordBook.word.in_(unique_words)
        )
        collection_existing = session.exec(collection_items_statement).all()
        collection_existing_words = {word.word for _, word in collection_existing}

        # 筛选出该单词本未导入的单词
        words_to_import = [w for w in unique_words if w not in collection_existing_words]

        if not words_to_import:
            # 所有单词该单词本都已经有了
            return {
                "imported": 0,
                "duplicates": len(collection_existing_words),
                "reused": 0,
                "llm_generated": 0,
                "total": len(unique_words),
                "failed": 0
            }

        # 第三步：检查数据库中是否已有这些单词（其他用户可能已导入）
        wordbook_statement = select(WordBook).where(WordBook.word.in_(words_to_import))
        existing_in_db = session.exec(wordbook_statement).all()
        existing_in_db_map = {w.word: w for w in existing_in_db}

        # 区分：可复用的单词 vs 需要LLM生成的新单词
        words_to_reuse = [w for w in words_to_import if w in existing_in_db_map]
        words_need_llm = [w for w in words_to_import if w not in existing_in_db_map]

        # 第四步：仅对数据库中不存在的单词调用LLM（节省token）
        newly_created_words = []
        failed_words = []

        if words_need_llm:
            try:
                # 调用大模型获取翻译
                translations = await llm_service.translate_words(words_need_llm)

                # 保存到数据库
                for word in words_need_llm:
                    if word in translations:
                        word_entry = WordBook(
                            word=word,
                            content=translations[word]
                        )
                        session.add(word_entry)
                        newly_created_words.append(word)
                    else:
                        failed_words.append(word)

                session.commit()
            except Exception as e:
                logger.error(f"LLM translation failed: {e}")
                # 如果批量翻译彻底失败，这些单词标记为失败
                failed_words.extend(words_need_llm)

        # 第五步：为用户在该单词本中创建学习条目
        # 5.1 处理复用的单词
        for word in words_to_reuse:
            word_entry = existing_in_db_map[word]
            item = UserWordItem(
                collection_id=collection_id,
                user_id=user.id,
                word_id=word_entry.id,
                status=0
            )
            session.add(item)

        # 5.2 处理新创建的单词
        if newly_created_words:
            # 需要重新查询以获取ID
            new_word_statement = select(WordBook).where(WordBook.word.in_(newly_created_words))
            new_word_entries = session.exec(new_word_statement).all()

            for word_entry in new_word_entries:
                item = UserWordItem(
                    collection_id=collection_id,
                    user_id=user.id,
                    word_id=word_entry.id,
                    status=0
                )
                session.add(item)

        session.commit()

        # 更新单词本的单词数量（由数据库触发器自动处理，这里只是刷新）
        session.refresh(collection)

        # 成功导入的数量 = 复用的 + 新生成的
        success_count = len(words_to_reuse) + len(newly_created_words)

        return {
            "imported": success_count,
            "duplicates": len(collection_existing_words),
            "reused": len(words_to_reuse),
            "llm_generated": len(newly_created_words),
            "total": len(unique_words),
            "failed": len(failed_words)
        }

    @staticmethod
    async def delete_word_item(
        item_id: uuid_pkg.UUID,
        user_id: uuid_pkg.UUID,
        session: Session
    ):
        """删除学习条目（不删除wordbook中的单词）"""
        statement = select(UserWordItem).where(
            UserWordItem.id == item_id,
            UserWordItem.user_id == user_id
        )
        item = session.exec(statement).first()

        if not item:
            raise HTTPException(status_code=404, detail="学习条目不存在")

        session.delete(item)
        session.commit()

    @staticmethod
    async def get_word_item(
        item_id: uuid_pkg.UUID,
        user_id: uuid_pkg.UUID,
        session: Session
    ) -> Dict[str, Any]:
        """获取学习条目详情"""
        statement = select(UserWordItem, WordBook).join(
            WordBook, UserWordItem.word_id == WordBook.id
        ).where(
            UserWordItem.id == item_id,
            UserWordItem.user_id == user_id
        )
        result = session.exec(statement).first()

        if not result:
            raise HTTPException(status_code=404, detail="学习条目不存在")

        item, word = result

        return {
            "item_id": item.id,
            "collection_id": item.collection_id,
            "word_id": word.id,
            "word": word.word,
            "content": word.content,
            "status": item.status,
            "review_count": item.review_count,
            "fail_count": item.fail_count,
            "match_count": item.match_count,
            "study_count": item.study_count,
            "last_review_time": item.last_review_time,
            "next_review_due": item.next_review_due,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
