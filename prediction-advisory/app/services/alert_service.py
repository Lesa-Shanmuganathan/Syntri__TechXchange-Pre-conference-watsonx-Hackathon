import uuid
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from app.services.forecasting import ForecastingService
from app.models.schemas import Alert, ActionTask
from app.config import settings
from app.database import get_sync_database
import logging

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self):
        self.forecasting_service = ForecastingService()
        self.db = get_sync_database()
    
    async def generate_daily_alert(self) -> Optional[Alert]:
        """Generate daily cash flow alert if needed"""
        forecasts = await self.forecasting_service.forecast_balance(settings.FORECAST_DAYS)
        
        if not forecasts:
            logger.warning("No forecasts available")
            return None
        
        has_breach, breach_info = await self.forecasting_service.detect_breach(
            forecasts, settings.CASH_MIN_THRESHOLD
        )
        
        if not has_breach:
            logger.info("No cash flow breach detected")
            return None
        
        # Generate prescriptive actions
        actions = await self._generate_actions(breach_info)
        
        # Create alert
        alert_id = f"alert_{uuid.uuid4().hex[:8]}"
        alert = Alert(
            alert_id=alert_id,
            anchor_date=date.today(),
            breach_date=breach_info['breach_date'],
            days_to_breach=breach_info['days_to_breach'],
            projected_balance=breach_info['projected_balance'],
            threshold=settings.CASH_MIN_THRESHOLD,
            severity=breach_info['severity'],
            actions=actions,
            raw_message=self._create_raw_message(breach_info, actions)
        )
        
        # Save to database
        alert_dict = alert.dict()
        alert_dict.pop('id', None)  # Remove the auto-generated id
        result = self.db.alerts.insert_one(alert_dict)
        alert.id = result.inserted_id
        
        return alert
    
    async def _generate_actions(self, breach_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate prescriptive actions based on breach info"""
        actions = []
        
        # Get recent outflows and receivables
        recent_outflows = list(self.db.financial_records.find({
            "type": "outflow",
            "date": {"$gte": date.today()},
            "amount": {"$gte": 1000}
        }).sort("amount", 1).limit(3))
        
        recent_receivables = list(self.db.financial_records.find({
            "type": "inflow",
            "due_date": {"$gte": date.today()},
            "amount": {"$gte": 1000}
        }).sort("due_date", 1).limit(3))
        
        # Action 1: Delay vendor payment
        if recent_outflows:
            vendor = recent_outflows[0]
            actions.append({
                "type": "delay_payment",
                "description": f"Delay {vendor.get('description', 'Vendor')} payment by 2 days",
                "amount": vendor['amount'],
                "target_id": vendor.get('vendor_id', 'V204'),
                "delay_days": 2,
                "impact": f"Keeps balance above ₹{settings.CASH_MIN_THRESHOLD + vendor['amount']:.0f}"
            })
        
        # Action 2: Early receivable collection
        if recent_receivables:
            receivable = recent_receivables[0]
            actions.append({
                "type": "early_collection",
                "description": f"Collect ₹{receivable['amount']:.0f} from {receivable.get('description', 'Client')} earlier",
                "amount": receivable['amount'],
                "target_id": receivable.get('client_id', 'C112'),
                "discount": 5,
                "impact": f"Improves balance by ₹{receivable['amount']:.0f}"
            })
        
        # Action 3: Pause subscription
        subscriptions = list(self.db.financial_records.find({
            "type": "outflow",
            "category": "subscription",
            "amount": {"$lt": 2000}
        }).sort("amount", -1).limit(1))
        
        if subscriptions:
            sub = subscriptions[0]
            actions.append({
                "type": "pause_subscription",
                "description": f"Pause non-essential subscription ₹{sub['amount']:.0f}",
                "amount": sub['amount'],
                "target_id": sub.get('vendor_id', 'SUB001'),
                "duration": "1 week",
                "impact": f"Saves ₹{sub['amount']:.0f}"
            })
        
        
        return actions[:3]  # Return max 3 actions
    
    def _create_raw_message(self, breach_info: Dict[str, Any], actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create raw message data for watsonx polishing"""
        return {
            "alert_date": date.today().strftime("%d %b %Y"),
            "breach_date": breach_info['breach_date'].strftime("%d %b"),
            "projected_balance": breach_info['projected_balance'],
            "threshold": settings.CASH_MIN_THRESHOLD,
            "days_to_breach": breach_info['days_to_breach'],
            "severity": breach_info['severity'],
            "actions": actions[:3],  # Max 3 actions for WhatsApp
            "currency": "₹"
        }
    
    async def simulate_action(self, alert_id: str, action_index: int) -> Dict[str, Any]:
        """Simulate an action and return results"""
        # Get alert
        alert_doc = self.db.alerts.find_one({"alert_id": alert_id})
        if not alert_doc:
            raise ValueError("Alert not found")
        
        # Get current forecasts
        forecasts = await self.forecasting_service.forecast_balance(settings.FORECAST_DAYS)
        
        # Get action
        if action_index >= len(alert_doc['actions']):
            raise ValueError("Invalid action index")
        
        action = alert_doc['actions'][action_index]
        
        # Simulate action
        simulated_forecasts = await self.forecasting_service.simulate_action(action, forecasts)
        
        # Check if breach is resolved
        has_breach, breach_info = await self.forecasting_service.detect_breach(
            simulated_forecasts, settings.CASH_MIN_THRESHOLD
        )
        
        return {
            "action": action,
            "resolves_breach": not has_breach,
            "new_min_balance": min(f.lower_bound for f in simulated_forecasts),
            "simulation_message": {
                "action_description": action['description'],
                "result": "resolved" if not has_breach else "improved",
                "new_breach_date": breach_info.get('breach_date') if has_breach else None,
                "min_balance": min(f.lower_bound for f in simulated_forecasts)
            }
        }
    
    async def confirm_action(self, alert_id: str, action_index: int) -> bool:
        """Confirm and log an action"""
        alert_doc = self.db.alerts.find_one({"alert_id": alert_id})
        if not alert_doc:
            return False
        
        if action_index >= len(alert_doc['actions']):
            return False
        
        action = alert_doc['actions'][action_index]
        
        # Create action task
        task = ActionTask(
            alert_id=alert_id,
            action_type=action['type'],
            description=action['description'],
            amount=action.get('amount'),
            target_id=action.get('target_id'),
            delay_days=action.get('delay_days'),
            status="confirmed"
        )
        
        task_dict = task.dict()
        task_dict.pop('id', None)
        self.db.action_tasks.insert_one(task_dict)
        
        # Update alert as actioned
        self.db.alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"actioned": True, "actioned_at": datetime.utcnow()}}
        )


        return True
