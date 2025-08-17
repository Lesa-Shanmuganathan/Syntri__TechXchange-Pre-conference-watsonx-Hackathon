#main
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from app.database import connect_to_mongo, close_mongo_connection
from app.services.alert_service import AlertService
from app.services.watsonx_service import WatsonxService
from app.services.whatsapp_service import WhatsAppService
from app.routers import alerts, webhooks
from app.utils.scheduler import setup_scheduler
from app.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Cash Flow Alert System...")
    await connect_to_mongo()
    
    # Setup background scheduler
    scheduler = setup_scheduler()
    scheduler.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()
    await close_mongo_connection()

app = FastAPI(
    title="Cash Flow Alert System",
    description="AI-powered cash flow forecasting and alerting system",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head>
            <title>Cash Flow Alert System</title>
        </head>
        <body>
            <h1>🚨 Cash Flow Alert System</h1>
            <p>AI-powered cash flow forecasting and alerting system for SMEs</p>
            <ul>
                <li><a href="/docs">API Documentation</a></li>
                <li><a href="/api/v1/alerts/test">Test Alert Generation</a></li>
                <li><a href="/api/v1/alerts/status">System Status</a></li>
            </ul>
        </body>
    </html>
    """

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "cash-flow-alert-system"

    }

