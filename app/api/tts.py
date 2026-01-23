"""TTS语音API"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, JSONResponse
from app.services.tts_service import tts_service
import logging

router = APIRouter(prefix="/api/tts", tags=["TTS语音"])
logger = logging.getLogger(__name__)


@router.get("/{word}")
async def get_word_audio(word: str):
    """获取单词发音"""
    try:
        audio_data = await tts_service.generate_audio(word)
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS error for word '{word}': {str(e)}")
        
        # 返回友好的错误信息而不是500错误
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "语音服务暂时不可用，请稍后重试",
                "error": "TTS_SERVICE_UNAVAILABLE",
                "word": word
            }
        )
