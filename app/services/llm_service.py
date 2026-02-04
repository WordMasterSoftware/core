"""大模型服务 - 支持用户级别配置（增强错误处理）"""
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
from typing import List, Dict, Any, Optional
import json
import asyncio
from app.utils.prompt_templates import (
    WORD_TRANSLATION_PROMPT,
    EXAM_GENERATION_PROMPT,
    TRANSLATION_GRADING_PROMPT
)
from app.models.user import User
from app.config import settings
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """LLM服务基础异常"""
    pass


class LLMAPIError(LLMServiceError):
    """LLM API调用错误"""
    pass


class LLMResponseParseError(LLMServiceError):
    """LLM响应解析错误"""
    pass


class LLMService:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        # Simple in-memory cache for translations: word -> translation_dict
        self._translation_cache = {}
        self._max_cache_size = 2000

    async def _safe_llm_call(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        timeout: float = 60.0,
        retries: int = 3
    ) -> Dict[str, Any]:
        """
        Generic safe LLM call with retry logic and error handling.
        """
        for attempt in range(retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    timeout=timeout
                )

                content = response.choices[0].message.content

                try:
                    # Clean up content if it contains markdown code blocks
                    cleaned_content = content.strip()
                    if cleaned_content.startswith("```json"):
                        cleaned_content = cleaned_content[7:]
                    if cleaned_content.startswith("```"):
                        cleaned_content = cleaned_content[3:]
                    if cleaned_content.endswith("```"):
                        cleaned_content = cleaned_content[:-3]

                    result = json.loads(cleaned_content.strip())
                    if not isinstance(result, (dict, list)):
                         # Only accept dict or list (though most prompts expect dict)
                         # However, generate_exam_sentences expects list in "sentences" key usually,
                         # but sometimes LLM returns just the list if prompted poorly.
                         # Our prompts ask for JSON objects usually.
                         pass
                    return result

                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing failed. Content: {content[:200]}...")
                    raise LLMResponseParseError(f"Failed to parse JSON response: {str(e)}")

            except AuthenticationError as e:
                logger.error(f"LLM Auth Error: {e}")
                raise LLMAPIError("Invalid API Key or Auth Error")

            except RateLimitError as e:
                if attempt < retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise LLMAPIError("Rate limit exceeded")

            except (APIConnectionError, asyncio.TimeoutError) as e:
                if attempt < retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Connection/Timeout error. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise LLMAPIError(f"Connection failed: {str(e)}")

            except APIError as e:
                logger.error(f"LLM API Error: {e}")
                raise LLMAPIError(f"API Error: {str(e)}")

            except Exception as e:
                logger.error(f"Unexpected LLM Error: {e}")
                raise LLMAPIError(f"Unexpected error: {str(e)}")

        raise LLMAPIError("Max retries exceeded")

    async def translate_words(
        self,
        words: List[str],
        batch_size: int = 20
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch translate words with caching.
        """
        if not words:
            return {}

        all_results = {}
        words_to_fetch = []

        # Check cache first
        for word in words:
            if word in self._translation_cache:
                all_results[word] = self._translation_cache[word]
            else:
                words_to_fetch.append(word)

        if not words_to_fetch:
            return all_results

        failed_words = []

        # Process missing words in batches
        for i in range(0, len(words_to_fetch), batch_size):
            batch = words_to_fetch[i:i + batch_size]
            try:
                batch_results = await self._translate_batch(batch)

                # Update cache
                for w, res in batch_results.items():
                    self._update_cache(w, res)

                all_results.update(batch_results)
            except LLMServiceError as e:
                logger.error(f"Batch translation failed for {batch}: {e}")
                failed_words.extend(batch)

        # Retry failed words individually
        if failed_words:
            logger.info(f"Retrying {len(failed_words)} failed words individually...")
            for word in failed_words:
                try:
                    single_result = await self._translate_batch([word])
                    for w, res in single_result.items():
                        self._update_cache(w, res)
                    all_results.update(single_result)
                except LLMServiceError:
                    pass # Skip if still failing

        return all_results

    def _update_cache(self, word: str, result: Dict):
        """Update cache with LRU-like eviction if full."""
        if len(self._translation_cache) >= self._max_cache_size:
            # Remove a random item or oldest (dict is ordered in Python 3.7+)
            # Simple approach: remove the first key (oldest inserted)
            try:
                first_key = next(iter(self._translation_cache))
                del self._translation_cache[first_key]
            except StopIteration:
                pass
        self._translation_cache[word] = result

    async def _translate_batch(self, words: List[str]) -> Dict[str, Dict[str, Any]]:
        """Translate a batch using safe LLM call."""
        prompt = WORD_TRANSLATION_PROMPT.format(words=", ".join(words))

        result = await self._safe_llm_call(
            messages=[
                {"role": "system", "content": "你是一个专业的英语词典助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        if not isinstance(result, dict):
             # Try to recover if it returns a list or something else, but prompt usually ensures dict
             raise LLMResponseParseError("Expected dictionary response")

        return result

    async def generate_exam_sentences(
        self,
        words: List[str],
        count: int = 10,
        sentence_count: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate exam sentences."""
        prompt = EXAM_GENERATION_PROMPT.format(
            count=count,
            sentence_count=sentence_count,
            words=", ".join(words)
        )

        result = await self._safe_llm_call(
            messages=[
                {"role": "system", "content": "你是一个专业的英语教师。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )

        return result.get("sentences", [])

    async def grade_translation(
        self,
        source_text: str,
        user_translation: str,
        required_words: List[str] = []
    ) -> Dict[str, Any]:
        """Grade translation."""
        prompt = TRANSLATION_GRADING_PROMPT.format(
            source_text=source_text,
            user_translation=user_translation,
            required_words=", ".join(required_words)
        )

        try:
            return await self._safe_llm_call(
                messages=[
                    {"role": "system", "content": "你是一个专业的英语评判老师。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=30.0
            )
        except LLMServiceError:
             # Fallback for grading as per requirement
             return {
                "correct": False,
                "feedback": "评判系统暂时不可用，请稍后再试"
            }


def get_llm_service_for_user(user: User) -> LLMService:
    """
    根据用户配置获取 LLM 服务实例
    - 如果用户选择使用默认配置，使用系统配置
    - 否则使用用户自定义配置
    """
    if user.use_default_llm:
        # 使用系统默认配置（从 .env）
        return LLMService(
            api_key=settings.DEFAULT_LLM_API_KEY,
            base_url=settings.DEFAULT_LLM_BASE_URL,
            model=settings.DEFAULT_LLM_MODEL
        )
    else:
        # 使用用户自定义配置
        return LLMService(
            api_key=user.llm_api_key or settings.DEFAULT_LLM_API_KEY,
            base_url=user.llm_base_url or settings.DEFAULT_LLM_BASE_URL,
            model=user.llm_model or settings.DEFAULT_LLM_MODEL
        )