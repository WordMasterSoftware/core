"""
FastAPI 主应用入口

该模块负责：
- 创建和配置 FastAPI 应用实例
- 注册中间件（CORS、速率限制）
- 注册所有 API 路由
- 配置受保护的 API 文档访问
- 应用生命周期管理
"""
import os
import secrets
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.api import auth, collections, dashboard, exam, messages, study, tts, words
from app.config import settings
from app.database import create_db_and_tables

# 创建速率限制器，基于客户端 IP 地址进行限制
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    启动时：
    - 创建数据库表
    - 创建 TTS 缓存目录
    - 打印启动信息
    """
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


# 创建 FastAPI 应用实例，禁用默认文档路由（使用自定义受保护路由）
app = FastAPI(
    title="WordMaster API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan
)

# 配置速率限制中间件
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(auth.router)          # 认证相关
app.include_router(collections.router)   # 单词本管理
app.include_router(words.router)         # 单词管理
app.include_router(study.router)         # 学习功能
app.include_router(exam.router)          # 考试功能
app.include_router(tts.router)           # 文本转语音
app.include_router(messages.router)      # 消息通知
app.include_router(dashboard.router)     # 仪表盘数据

# HTTP Basic 认证，用于保护 API 文档
security = HTTPBasic()


def check_admin_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """
    验证 API 文档访问权限

    使用 HTTP Basic 认证，密码必须与 DEV_TOKEN 匹配

    Args:
        credentials: HTTP Basic 认证凭据

    Returns:
        验证通过返回用户名

    Raises:
        HTTPException: 认证失败或文档已禁用
    """
    from fastapi import HTTPException

    if not settings.DEV_TOKEN:
        raise HTTPException(status_code=404, detail="文档已禁用")

    if not secrets.compare_digest(credentials.password, settings.DEV_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="管理员令牌错误",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(username: str = Depends(check_admin_auth)):
    """获取 Swagger UI 文档页面"""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="WordMaster API - Docs")


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(username: str = Depends(check_admin_auth)):
    """获取 ReDoc 文档页面"""
    return get_redoc_html(openapi_url="/openapi.json", title="WordMaster API - ReDoc")


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(username: str = Depends(check_admin_auth)):
    """获取 OpenAPI JSON 规范"""
    return JSONResponse(get_openapi(title="WordMaster API", version="1.0.0", routes=app.routes))


@app.get("/")
async def root() -> dict:
    """API 根路径，返回基本信息"""
    return {
        "message": "欢迎使用 WordMaster API",
        "version": "1.0.0",
        "docs": "/docs" if settings.DEV_TOKEN else "disabled"
    }


@app.get("/health")
async def health_check() -> dict:
    """健康检查接口"""
    return {"status": "healthy", "service": "WordMaster API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
