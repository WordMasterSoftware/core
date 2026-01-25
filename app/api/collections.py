"""单词本管理API"""
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlmodel import Session
from app.database import get_session
from app.schemas.collection import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionListResponse,
    WordsImportToCollection,
    WordsImportTaskResponse
)
from app.schemas.marketplace import MarketplaceBookImport
from app.services.collection_service import CollectionService
from app.services.word_service import WordService
from app.utils.dependencies import get_current_user
from app.models import User
import uuid as uuid_pkg

router = APIRouter(prefix="/api/collections", tags=["单词本管理"])


@router.post("", response_model=CollectionResponse)
async def create_collection(
    collection_data: CollectionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """创建单词本"""
    collection = await CollectionService.create_collection(
        user_id=current_user.id,
        name=collection_data.name,
        description=collection_data.description,
        color=collection_data.color,
        icon=collection_data.icon,
        session=session
    )
    return collection


@router.get("", response_model=CollectionListResponse)
async def get_collections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """获取用户的所有单词本"""
    result = await CollectionService.get_user_collections(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        session=session
    )
    return result


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: uuid_pkg.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """获取单个单词本"""
    collection = await CollectionService.get_collection(
        collection_id=collection_id,
        user_id=current_user.id,
        session=session
    )
    return collection


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: uuid_pkg.UUID,
    collection_data: CollectionUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """更新单词本"""
    collection = await CollectionService.update_collection(
        collection_id=collection_id,
        user_id=current_user.id,
        name=collection_data.name,
        description=collection_data.description,
        color=collection_data.color,
        icon=collection_data.icon,
        session=session
    )
    return collection


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: uuid_pkg.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """删除单词本（级联删除所有学习条目）"""
    await CollectionService.delete_collection(
        collection_id=collection_id,
        user_id=current_user.id,
        session=session
    )
    return {
        "success": True,
        "message": "单词本已删除"
    }


@router.post("/{collection_id}/import", response_model=WordsImportTaskResponse, status_code=202)
async def import_words_to_collection(
    collection_id: uuid_pkg.UUID,
    import_request: WordsImportToCollection,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    导入单词到指定单词本 (异步任务)

    - 提交后立即返回任务ID
    - 后台进行去重、LLM生成和入库
    - 完成后会发送站内消息通知
    """
    # 验证 collection_id 匹配
    if import_request.collection_id != collection_id:
        raise HTTPException(status_code=400, detail="URL中的ID与请求体中的ID不一致")

    # 简单验证单词本是否存在 (快速失败)
    await CollectionService.get_collection(collection_id, current_user.id, session)

    # 生成任务ID
    task_id = uuid_pkg.uuid4()

    # 添加后台任务
    background_tasks.add_task(
        WordService.import_words_background_task,
        user_id=current_user.id,
        collection_id=collection_id,
        words=import_request.words
    )

    return WordsImportTaskResponse(
        success=True,
        message="导入任务已提交，请稍后在消息中心查看结果",
        task_id=task_id
    )


@router.post("/import-json", response_model=WordsImportTaskResponse, status_code=202)
async def import_marketplace_json(
    import_request: MarketplaceBookImport,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    从 Marketplace JSON 导入并自动创建单词本 (异步任务)

    - 接收完整的 Marketplace JSON 数据
    - 自动创建一个同名单词本
    - 后台复用 JSON 中的释义导入单词，不消耗 LLM Token
    """
    # 1. 自动创建单词本
    collection = await CollectionService.create_collection(
        user_id=current_user.id,
        name=import_request.name,
        description=import_request.description,
        color=import_request.color or "#3B82F6",
        icon=import_request.icon or "BookOpenIcon",
        session=session
    )

    # 2. 生成任务ID
    task_id = uuid_pkg.uuid4()

    # 3. 添加后台任务
    background_tasks.add_task(
        WordService.import_marketplace_book_background_task,
        user_id=current_user.id,
        collection_id=collection.id,
        marketplace_data=import_request.model_dump()
    )

    return WordsImportTaskResponse(
        success=True,
        message=f"已创建单词本 '{collection.name}' 并开始导入",
        task_id=task_id
    )


@router.get("/{collection_id}/words")
async def get_collection_words(
    collection_id: uuid_pkg.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """获取单词本中的所有单词（带学习进度）"""
    result = await CollectionService.get_collection_words(
        collection_id=collection_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        session=session
    )
    return result
