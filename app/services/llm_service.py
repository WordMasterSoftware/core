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

    async def translate_words(
        self,
        words: List[str],
        batch_size: int = 20
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量翻译单词（增强错误处理）

        Args:
            words: 单词列表
            batch_size: 批次大小，默认20个单词一批

        Returns:
            成功翻译的单词字典

        Raises:
            LLMAPIError: API调用错误
            LLMResponseParseError: 响应解析错误
        """
        if not words:
            return {}

        all_results = {}
        failed_words = []

        # 分批处理，避免单次请求过大
        for i in range(0, len(words), batch_size):
            batch = words[i:i + batch_size]
            try:
                batch_results = await self._translate_batch(batch)
                all_results.update(batch_results)
            except LLMServiceError as e:
                logger.error(f"Batch translation failed for words {batch}: {e}")
                failed_words.extend(batch)

        # 如果有失败的单词，尝试逐个翻译
        if failed_words:
            logger.info(f"Retrying {len(failed_words)} failed words individually...")
            for word in failed_words:
                try:
                    single_result = await self._translate_batch([word])
                    all_results.update(single_result)
                except LLMServiceError as e:
                    logger.error(f"Failed to translate word '{word}': {e}")
                    # 继续处理其他单词，不中断整个流程

        return all_results

    async def _translate_batch(self, words: List[str]) -> Dict[str, Dict[str, Any]]:
        """翻译一批单词（带重试机制）"""
        prompt = WORD_TRANSLATION_PROMPT.format(words=", ".join(words))

        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的英语词典助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    timeout=60.0  # 60秒超时
                )

                content = response.choices[0].message.content

                # 尝试解析 JSON
                try:
                    result = json.loads(content)

                    # 验证返回的数据格式
                    if not isinstance(result, dict):
                        raise LLMResponseParseError("LLM返回的不是字典格式")

                    return result

                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败，原始内容: {content[:200]}")
                    raise LLMResponseParseError(f"无法解析LLM返回的JSON: {str(e)}")

            except AuthenticationError as e:
                # 认证错误不需要重试
                logger.error(f"LLM API认证失败: {e}")
                raise LLMAPIError("LLM API密钥无效或已过期，请检查配置")

            except RateLimitError as e:
                # 速率限制错误，等待后重试
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # 指数退避
                    logger.warning(f"LLM API速率限制，等待{wait_time}秒后重试...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"LLM API速率限制，重试次数已用完: {e}")
                    raise LLMAPIError("LLM API调用频率过高，请稍后再试")

            except APIConnectionError as e:
                # 网络连接错误，重试
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"LLM API连接失败，{wait_time}秒后重试（{attempt + 1}/{self.max_retries}）...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"LLM API连接失败，重试次数已用完: {e}")
                    raise LLMAPIError("无法连接到LLM服务，请检查网络或API地址配置")

            except APIError as e:
                # 其他API错误
                logger.error(f"LLM API错误: {e}")
                raise LLMAPIError(f"LLM API调用失败: {str(e)}")

            except asyncio.TimeoutError:
                # 超时错误
                if attempt < self.max_retries - 1:
                    logger.warning(f"LLM API超时，重试中（{attempt + 1}/{self.max_retries}）...")
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    logger.error("LLM API超时，重试次数已用完")
                    raise LLMAPIError("LLM API响应超时，请稍后再试")

            except Exception as e:
                # 未知错误
                logger.error(f"LLM翻译时发生未知错误: {type(e).__name__}: {e}")
                raise LLMAPIError(f"LLM服务异常: {str(e)}")

        # 理论上不会到达这里
        raise LLMAPIError("LLM API调用失败")

    async def generate_exam_sentences(
        self,
        words: List[str],
        count: int = 10,
        sentence_count: int = 5
    ) -> List[Dict[str, Any]]:
        """生成考试句子（增强错误处理）"""
        prompt = EXAM_GENERATION_PROMPT.format(
            count=count,
            sentence_count=sentence_count,
            words=", ".join(words)
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的英语教师。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                timeout=60.0
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            return result.get("sentences", [])

        except json.JSONDecodeError as e:
            logger.error(f"考试句子生成JSON解析失败: {e}")
            raise LLMResponseParseError("无法解析LLM生成的考试内容")

        except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as e:
            logger.error(f"考试句子生成API错误: {e}")
            raise LLMAPIError(f"考试生成失败: {str(e)}")

        except Exception as e:
            logger.error(f"考试句子生成未知错误: {e}")
            raise LLMAPIError(f"考试生成异常: {str(e)}")

    async def grade_translation(
        self,
        english_sentence: str,
        user_translation: str
    ) -> Dict[str, Any]:
        """评判翻译（增强错误处理）"""
        prompt = TRANSLATION_GRADING_PROMPT.format(
            english_sentence=english_sentence,
            user_translation=user_translation
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的英语评判老师。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=30.0
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"翻译评判JSON解析失败: {e}")
            # 降级策略：返回默认结果
            return {
                "correct": False,
                "feedback": "评判系统暂时不可用，请稍后再试"
            }

        except Exception as e:
            logger.error(f"翻译评判错误: {e}")
            # 降级策略：返回默认结果
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