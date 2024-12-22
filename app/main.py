# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, List
import logging
import time
from app.models.logger import logger
from app.core.request_handler import RequestHandler
from app.models.schemas import (
    EnhancedModelConfig,
    CompletionRequest,
    CompletionResponse,
    ApiKeyConfig
)
from app.models.model_manager import ModelManager
from app.models.database import Database
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_time = time.time()
    logger.info("Starting application", extra={
        "env": settings.ENV,
        "debug_mode": settings.DEBUG,
        "service_name": settings.SERVICE_NAME
    })
    
    try:
        # Initialize database
        logger.info("Initializing database connection")
        app.state.db = Database()
        
        # Initialize model manager
        logger.info("Initializing model manager")
        model_manager = ModelManager()
        await model_manager.init_default_configs()
        
        startup_time = time.time() - start_time
        logger.info("Application startup completed", extra={
            "startup_time": startup_time,
            "database_status": "connected",
            "redis_status": "connected"
        })
        
        yield
        
    except Exception as e:
        logger.error("Application startup failed", extra={
            "error": str(e),
            "startup_time": time.time() - start_time
        })
        raise
    finally:
        # Shutdown
        logger.info("Initiating application shutdown")
        if hasattr(app.state, "db"):
            app.state.db.client.close()
            logger.info("Database connection closed")
        logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """Initialize and configure the FastAPI application"""
    app = FastAPI(
        title="AI Model Proxy Service",
        description="Unified API proxy for various AI model providers",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, replace with specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app

app = create_app()

# Dependency for API key validation
async def validate_api_key(
    api_key: str = Header(..., description="API Key for authentication")
) -> str:
    if not api_key.startswith(settings.API_KEY_PREFIX):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key format"
        )
    return api_key

# Enhanced request processing time middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    request_id = str(time.time())
    start_time = time.time()
    
    logger.info("Request received", extra={
        "request_id": request_id,
        "method": request.method,
        "url": str(request.url),
        "client_host": request.client.host if request.client else None
    })
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_id
        
        logger.info("Request completed", extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "process_time": process_time
        })
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error("Request failed", extra={
            "request_id": request_id,
            "error": str(e),
            "process_time": process_time
        })
        raise
    # Enhanced error handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = str(time.time())
    
    logger.error("HTTP exception occurred", extra={
        "request_id": request_id,
        "status_code": exc.status_code,
        "error_detail": exc.detail,
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "type": "api_error",
                "code": exc.status_code,
                "request_id": request_id
            }
        }
    )


# Enhanced route handlers
@app.post("/v1/chat/completions")
async def create_chat_completion(
    request: CompletionRequest,
    api_key: str = Depends(validate_api_key)
):
    request_id = str(time.time())
    
    logger.info("Chat completion request received", extra={
        "request_id": request_id,
        "model": request.model,
        "api_key": api_key
    })
    
    try:
        handler = RequestHandler()
        response = await handler.handle_request(request.dict(), api_key)
        
        logger.info("Chat completion request succeeded", extra={
            "request_id": request_id,
            "model": request.model,
            "tokens": response.get("usage", {}),
            "api_key": api_key
        })
        
        return response
    except Exception as e:
        logger.error("Chat completion request failed", extra={
            "request_id": request_id,
            "model": request.model,
            "error": str(e),
            "api_key": api_key
        })
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get(
    "/v1/models",
    response_model=List[EnhancedModelConfig],
    description="List all available models"
)
async def list_models(api_key: str = Depends(validate_api_key)):
    model_manager = ModelManager()
    try:
        return await model_manager.get_active_models()
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/v1/models/{model_id}",
    response_model=EnhancedModelConfig,
    description="Get details for a specific model"
)
async def get_model(
    model_id: str,
    api_key: str = Depends(validate_api_key)
):
    model_manager = ModelManager()
    model = await model_manager.get_model_config(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "timestamp": time.time()}

# Admin routes (require admin API key)
async def validate_admin_key(api_key: str = Depends(validate_api_key)):
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Admin API key required"
        )
    return api_key

@app.put(
    "/v1/admin/models/{model_id}",
    response_model=EnhancedModelConfig,
    description="Update model configuration (Admin only)"
)
async def update_model(
    model_id: str,
    updates: Dict,
    api_key: str = Depends(validate_admin_key)
):
    model_manager = ModelManager()
    try:
        await model_manager.update_model_config(model_id, updates)
        return await model_manager.get_model_config(model_id)
    except Exception as e:
        logger.error(f"Error updating model config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",  # 修改这里，使用正确的模块路径
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )