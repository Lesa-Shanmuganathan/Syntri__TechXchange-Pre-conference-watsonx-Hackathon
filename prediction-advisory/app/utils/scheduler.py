from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import logging

from app.services.alert_service import AlertService
from app.services.watsonx_service import WatsonxService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

async def daily_alert_job():
    """Daily job to check for cash flow alerts"""
    logger.info("Running daily alert job...")
    
    try:
        alert_service = AlertService()
        watsonx_service = WatsonxService()
        whatsapp_service = WhatsAppService()
        
        # Generate alert if needed
        alert = await alert_service.generate_daily_alert()
        
        if alert:
            # Polish message
            polished_message = await watsonx_service.polish_alert_message(
                alert.raw_message, alert.alert_id
            )
            
            # Send via WhatsApp (demo number)
            demo_number = "+919876543210"  # Replace with actual demo number
            success = await whatsapp_service.send_alert(polished_message, demo_number)
            
            if success:
                logger.info(f"Daily alert sent successfully: {alert.alert_id}")
            else:
                logger.error("Failed to send daily alert")
        else:
            logger.info("No alert needed today")
            
    except Exception as e:
        logger.error(f"Daily alert job failed: {e}")

def setup_scheduler() -> AsyncIOScheduler:
    """Setup background scheduler for daily alerts"""
    scheduler = AsyncIOScheduler()
    
    # Schedule daily alert check at 9 AM
    scheduler.add_job(
        daily_alert_job,
        CronTrigger(hour=9, minute=0),
        id="daily_alert_check",
        replace_existing=True
    )
    
    # For demo purposes, also run every 2 hours during demo period
    scheduler.add_job(
        daily_alert_job,
        CronTrigger(minute=0, second=0),  # Every hour at minute 0
        id="demo_alert_check",
        replace_existing=True
    )
    
    logger.info("Background scheduler configured")
    return scheduler