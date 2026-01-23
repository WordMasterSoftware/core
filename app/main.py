"""FastAPI 主应用"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import create_db_and_tables
from app.api import auth, words, study, exam, tts, collections, messages
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时执行
    create_db_and_tables()
    os.makedirs(settings.TTS_CACHE_DIR, exist_ok=True)

    print("🚀 WordMaster API 已启动")
    print(f"📚 数据库: {settings.DATABASE_URL}")
    print(f"🌐 允许的源: {settings.ALLOWED_ORIGINS}")
    print(f"🤖 大模型: {settings.DEFAULT_LLM_MODEL}")
    print(f"📖 API 文档: http://{settings.HOST}:{settings.PORT}/docs")

    yield

    # 关闭时执行（如有需要）


# 创建FastAPI应用
app = FastAPI(
    title="WordMaster API",
    description="""
    ## 智能背单词系统后端API

    ### 认证说明
    大部分 API 需要 JWT 认证。请先：
    1. 调用 `/api/auth/register` 注册用户
    2. 或调用 `/api/auth/login` 登录
    3. 复制返回的 `token`
    4. 点击右上角 🔓 **Authorize** 按钮
    5. 在弹出框中输入：`Bearer <你的token>`
    6. 点击 Authorize 确认

    之后即可测试需要认证的 API。
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(collections.router)  # 单词本管理 (新增)
app.include_router(words.router)
app.include_router(study.router)
app.include_router(exam.router)
app.include_router(tts.router)
app.include_router(messages.router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to WordMaster API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "WordMaster API"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
