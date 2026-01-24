from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.database import get_session
from app.utils.dependencies import get_current_user
from app.models import User
from app.services.dashboard_service import DashboardService
from app.schemas.dashboard import DashboardStatsResponse

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard statistics for the current user"""
    stats = await DashboardService.get_stats(current_user.id, session)
    return stats
