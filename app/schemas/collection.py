"""单词本相关的 Schema"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid as uuid_pkg


# 创建单词本请求
class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="单词本名称")
    description: Optional[str] = Field(None, description="单词本描述")
    color: Optional[str] = Field(None, max_length=20, description="颜色标识")
    icon: Optional[str] = Field(None, max_length=50, description="图标标识")


# 更新单词本请求
class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="单词本名称")
    description: Optional[str] = Field(None, description="单词本描述")
    color: Optional[str] = Field(None, max_length=20, description="颜色标识")
    icon: Optional[str] = Field(None, max_length=50, description="图标标识")


# 单词本响应
class CollectionResponse(BaseModel):
    id: uuid_pkg.UUID
    user_id: uuid_pkg.UUID
    name: str
    description: Optional[str]
    color: Optional[str]
    icon: Optional[str]
    word_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 单词本列表响应
class CollectionListResponse(BaseModel):
    total: int
    collections: list[CollectionResponse]
    page: int
    page_size: int


# 导入单词到单词本请求
class WordsImportToCollection(BaseModel):
    collection_id: uuid_pkg.UUID = Field(..., description="目标单词本ID")
    words: list[str] = Field(..., min_items=1, description="单词列表")


# 导入任务响应 (异步结果)
class WordsImportTaskResponse(BaseModel):
    success: bool
    message: str
    task_id: uuid_pkg.UUID