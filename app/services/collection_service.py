"""单词本管理服务"""
from sqlmodel import Session, select
from sqlalchemy import func
from app.models import WordCollection, UserWordItem, WordBook
from typing import Dict, Any
import uuid as uuid_pkg
from fastapi import HTTPException


class CollectionService:
    @staticmethod
    async def create_collection(
        user_id: uuid_pkg.UUID,
        name: str,
        description: str = None,
        color: str = None,
        icon: str = None,
        session: Session = None
    ) -> WordCollection:
        """创建单词本"""
        collection = WordCollection(
            user_id=user_id,
            name=name,
            description=description,
            color=color,
            icon=icon,
            word_count=0
        )
        session.add(collection)
        session.commit()
        session.refresh(collection)
        return collection

    @staticmethod
    async def get_user_collections(
        user_id: uuid_pkg.UUID,
        page: int,
        page_size: int,
        session: Session
    ) -> Dict[str, Any]:
        """获取用户的所有单词本"""
        # 计算偏移量
        offset = (page - 1) * page_size

        # 查询用户的单词本
        statement = select(WordCollection).where(
            WordCollection.user_id == user_id
        ).offset(offset).limit(page_size).order_by(WordCollection.created_at.desc())

        collections = session.exec(statement).all()

        # 为每个单词本动态计算word_count
        for collection in collections:
            count_statement = select(func.count()).select_from(UserWordItem).where(
                UserWordItem.collection_id == collection.id
            )
            word_count = session.exec(count_statement).one()
            collection.word_count = word_count

        # 统计总数
        count_statement = select(func.count()).select_from(WordCollection).where(WordCollection.user_id == user_id)
        total = session.exec(count_statement).one()

        return {
            "total": total,
            "collections": collections,
            "page": page,
            "page_size": page_size
        }

    @staticmethod
    async def get_collection(
        collection_id: uuid_pkg.UUID,
        user_id: uuid_pkg.UUID,
        session: Session
    ) -> WordCollection:
        """获取单个单词本"""
        statement = select(WordCollection).where(
            WordCollection.id == collection_id,
            WordCollection.user_id == user_id
        )
        collection = session.exec(statement).first()

        if not collection:
            raise HTTPException(status_code=404, detail="单词本不存在")

        # 动态计算word_count
        count_statement = select(func.count()).select_from(UserWordItem).where(
            UserWordItem.collection_id == collection_id
        )
        word_count = session.exec(count_statement).one()
        collection.word_count = word_count

        return collection

    @staticmethod
    async def update_collection(
        collection_id: uuid_pkg.UUID,
        user_id: uuid_pkg.UUID,
        name: str = None,
        description: str = None,
        color: str = None,
        icon: str = None,
        session: Session = None
    ) -> WordCollection:
        """更新单词本"""
        collection = await CollectionService.get_collection(collection_id, user_id, session)

        if name is not None:
            collection.name = name
        if description is not None:
            collection.description = description
        if color is not None:
            collection.color = color
        if icon is not None:
            collection.icon = icon

        session.add(collection)
        session.commit()
        session.refresh(collection)
        return collection

    @staticmethod
    async def delete_collection(
        collection_id: uuid_pkg.UUID,
        user_id: uuid_pkg.UUID,
        session: Session
    ):
        """删除单词本（级联删除所有学习条目）"""
        collection = await CollectionService.get_collection(collection_id, user_id, session)

        session.delete(collection)
        session.commit()

    @staticmethod
    async def get_collection_words(
        collection_id: uuid_pkg.UUID,
        user_id: uuid_pkg.UUID,
        page: int,
        page_size: int,
        session: Session
    ) -> Dict[str, Any]:
        """获取单词本中的所有单词（带学习进度）"""
        # 验证单词本所有权
        await CollectionService.get_collection(collection_id, user_id, session)

        # 计算偏移量
        offset = (page - 1) * page_size

        # 查询单词本中的单词
        statement = select(UserWordItem, WordBook).join(
            WordBook, UserWordItem.word_id == WordBook.id
        ).where(
            UserWordItem.collection_id == collection_id
        ).offset(offset).limit(page_size).order_by(UserWordItem.created_at.desc())

        results = session.exec(statement).all()

        # 统计总数
        count_statement = select(func.count()).select_from(UserWordItem).where(
            UserWordItem.collection_id == collection_id
        )
        total = session.exec(count_statement).one()

        words = []
        for item, word in results:
            words.append({
                "item_id": item.id,
                "word_id": word.id,
                "word": word.word,
                "content": word.content,
                "status": item.status,
                "review_count": item.review_count,
                "fail_count": item.fail_count,
                "study_count": item.study_count,
                "last_review_time": item.last_review_time,
                "created_at": item.created_at
            })

        return {
            "total": total,
            "words": words,
            "page": page,
            "page_size": page_size
        }