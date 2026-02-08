"""FastAPI 主应用"""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.database import create_db_and_tables
from app.api import auth, words, study, exam, tts, collections, messages, dashboard
import os
import secrets
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# 创建速率限制器（基于客户端IP）
limiter = Limiter(key_func=get_remote_address)


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
    if settings.DEV_TOKEN:
        print(f"📖 API 文档 (受保护): http://{settings.HOST}:{settings.PORT}/docs")
    else:
        print("⚠️ DEV_TOKEN 未配置，API 文档已禁用")

    yield

    # 关闭时执行（如有需要）


# 创建FastAPI应用 - 禁用默认文档路由
app = FastAPI(
    title="WordMaster API",
    version="1.0.0",
    docs_url=None,  # 禁用默认 docs
    redoc_url=None, # 禁用默认 redoc
    openapi_url=None, # 禁用默认 openapi.json
    lifespan=lifespan
)

# 配置速率限制
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(dashboard.router)

# --- 文档保护逻辑 ---
security = HTTPBasic()

def check_admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """验证文档访问权限"""
    if not settings.DEV_TOKEN:
        raise HTTPException(
            status_code=404,
            detail="Documentation disabled (DEV_TOKEN not set)"
        )

    # 用户名随意，密码必须是 DEV_TOKEN
    is_correct_token = secrets.compare_digest(credentials.password, settings.DEV_TOKEN)
    if not is_correct_token:
        raise HTTPException(
            status_code=401,
            detail="Incorrect admin token",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(username: str = Depends(check_admin_auth)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="WordMaster API - Docs")

@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(username: str = Depends(check_admin_auth)):
    return get_redoc_html(openapi_url="/openapi.json", title="WordMaster API - ReDoc")

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(username: str = Depends(check_admin_auth)):
    return JSONResponse(get_openapi(title="WordMaster API", version="1.0.0", routes=app.routes))
# --------------------


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to WordMaster API",
        "version": "1.0.0",
        "docs": "/docs" if settings.DEV_TOKEN else "disabled"
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
