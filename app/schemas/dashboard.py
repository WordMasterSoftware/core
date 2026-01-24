from pydantic import BaseModel

class DashboardStatsResponse(BaseModel):
    total_words: int
    total_collections: int
    today_learned: int
    to_review: int
