"""
FastAPI Application Entry Point for AI Operations Assistant.
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.routes import router as api_router
from config import get_settings
from utils.logger import setup_logging, get_logger
from tools.registry import get_tool_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    settings = get_settings()
    setup_logging(settings.log_level, json_format=False)
    logger = get_logger(__name__)
    
    logger.info("AI Operations Assistant starting up...")
    
    # Initialize tool registry
    registry = get_tool_registry()
    logger.info(f"Loaded {len(registry.get_all())} tools: {registry.get_tool_names()}")
    
    yield
    
    # Shutdown
    logger.info("AI Operations Assistant shutting down...")
    await registry.close_all()


# Create FastAPI app
app = FastAPI(
    title="AI Operations Assistant",
    description="""
    **Multi-Agent AI System** for executing natural language tasks.
    
    ## Features
    - **Planner Agent**: Converts tasks to execution plans
    - **Executor Agent**: Calls tools and APIs
    - **Verifier Agent**: Validates and formats results
    
    ## Available Tools
    - **GitHub**: Search repos, get details, user info
    - **Weather**: Current weather, forecasts
    - **News**: Headlines, article search
    
    ## Usage
    POST a task to `/api/v1/task` with natural language like:
    > "Get weather in Tokyo and find top Python AI repositories"
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = get_logger(__name__)
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


# Include API routes
app.include_router(api_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with welcome message."""
    return {
        "message": "AI Operations Assistant",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    settings = get_settings()
    
    print("""
    ================================================================
    |           AI Operations Assistant                            |
    |                                                              |
    |   Multi-agent system for natural language task execution     |
    |                                                              |
    |   API Docs:  http://localhost:8000/docs                      |
    |   Health:    http://localhost:8000/api/v1/health             |
    ================================================================
    """)
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )
