from typing import List, Optional
from pydantic import BaseModel

class MarketplaceWordEntry(BaseModel):
    word: str
    chinese: str
    phonetic: Optional[str] = None
    part_of_speech: Optional[str] = None
    sentences: List[str] = []

class MarketplaceBookImport(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#3B82F6"  # 默认蓝色
    icon: Optional[str] = "BookOpenIcon" # 默认图标
    words: List[MarketplaceWordEntry]
