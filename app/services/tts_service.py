"""TTS 语音服务"""
import edge_tts
from pathlib import Path
from app.config import settings
import hashlib
import asyncio


class TTSService:
    def __init__(self):
        self.voice = settings.TTS_VOICE
        self.rate = settings.TTS_RATE
        self.cache_dir = Path(settings.TTS_CACHE_DIR)
        self.cache_dir.mkdir(exist_ok=True)
    
    async def generate_audio(self, word: str) -> bytes:
        """生成单词音频"""
        # 生成缓存文件名
        word_hash = hashlib.md5(word.encode()).hexdigest()
        cache_file = self.cache_dir / f"{word_hash}.mp3"
        
        # 检查缓存
        if cache_file.exists():
            return cache_file.read_bytes()
        
        # 生成音频
        try:
            # 添加重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    communicate = edge_tts.Communicate(word, self.voice, rate=self.rate)
                    await communicate.save(str(cache_file))
                    
                    # 验证文件是否生成成功
                    if cache_file.exists() and cache_file.stat().st_size > 0:
                        return cache_file.read_bytes()
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        # 等待后重试
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise
            
            # 如果所有重试都失败，返回空的音频提示
            raise Exception("Failed to generate audio after retries")
            
        except Exception as e:
            print(f"TTS generation error for word '{word}': {e}")
            # 返回一个默认的错误提示
            # 实际应用中可以返回一个静默的音频文件或抛出 HTTP 异常
            raise


tts_service = TTSService()
