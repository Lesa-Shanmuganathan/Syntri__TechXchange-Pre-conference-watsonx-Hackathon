from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any
from datetime import date
import logging

from app.services.alert_service import AlertService
from app.services.watsonx_service import WatsonxService
from app.services.whatsapp_service import WhatsAppService
from app.models.schemas import Alert, SimulationRequest, SimulationResponse

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/alerts/test")
async def test_alert_generation():
    """Test endpoint to generate and return an alert"""
    alert_service = AlertService()
    watsonx_service = WatsonxService()
    
    try:
        alert = await alert_service.generate_daily_alert()
        if not alert:
            return {"message": "No alert needed - cash flow is healthy"}
        
        # Polish the message
        polished_message = await watsonx_service.polish_alert_message(
            alert.raw_message, alert.alert_id
        )
        
        return {
            "alert_id": alert.alert_id,
            "breach_date": alert.breach_date,
            "days_to_breach": alert.days_to_breach,
            "projected_balance": alert.projected_balance,
            "threshold": alert.threshold,
            "severity": alert.severity,
            "actions": alert.actions,
            "polished_message": polished_message
        }
    except Exception as e:
        logger.error(f"Test alert generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/simulate")
async def simulate_action(request: SimulationRequest):
    """Simulate an action and return results"""
    alert_service = AlertService()
    watsonx_service = WatsonxService()
    
    try:
        simulation_result = await alert_service.simulate_action(
            request.alert_id, request.action_index
        )
        
        # Polish simulation message
        polished_message = await watsonx_service.polish_simulation_message(
            simulation_result['simulation_message']
        )
        
        return {
            "success": True,
            "message": polished_message,
            "resolves_breach": simulation_result['resolves_breach'],
            "new_min_balance": simulation_result['new_min_balance']
        }
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/confirm/{alert_id}/{action_index}")
async def confirm_action(alert_id: str, action_index: int):
    """Confirm an action"""
    alert_service = AlertService()
    
    try:
        success = await alert_service.confirm_action(alert_id, action_index)
        if success:
            return {
                "success": True,
                "message": "✅ Action confirmed. We've scheduled the task and will remind you as needed."
            }
        else:
            raise HTTPException(status_code=404, detail="Alert or action not found")
    except Exception as e:
        logger.error(f"Action confirmation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts/status")
async def system_status():
    """Get system status"""
    from app.database import get_sync_database
    
    try:
        db = get_sync_database()
        
        # Get counts
        alerts_count = db.alerts.count_documents({})
        records_count = db.financial_records.count_documents({})
        tasks_count = db.action_tasks.count_documents({})
        
        # Get recent activity
        recent_alerts = list(db.alerts.find({}).sort("created_at", -1).limit(5))
        
        return {
            "system_status": "healthy",
            "database_status": "connected",
            "statistics": {
                "total_alerts": alerts_count,
                "financial_records": records_count,
                "action_tasks": tasks_count
            },
            "recent_activity": len(recent_alerts)
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))