from fastapi import APIRouter, Request
from fastapi.responses import Response
import logging

from app.services.alert_service import AlertService
from app.services.watsonx_service import WatsonxService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages"""
    form_data = await request.form()
    incoming_message = form_data.get('Body', '').strip().lower()
    from_number = form_data.get('From', '').replace('whatsapp:', '')

    logger.info(f"Received WhatsApp message: {incoming_message} from {from_number}")

    alert_service = AlertService()
    watsonx_service = WatsonxService()
    whatsapp_service = WhatsAppService()

    try:
        if incoming_message == "status":
            # Simulate fetching a cash flow alert for the user
            alert_message = (
                "🚨 *Cash Flow Alert!*\n\n"
                "Your projected balance for 17 Aug is *₹-1,20,000*.\n"
                "Recommended actions:\n"
                "1️⃣ Delay Vendor V204 by 2 days\n"
                "2️⃣ Request early payment from Customer C102\n"
                "3️⃣ Reduce discretionary spend this week\n\n"
                "Reply with 1, 2, or 3 to simulate an action."
            )
            response_message = alert_message

        elif incoming_message.isdigit() and incoming_message in {"1", "2", "3"}:
            action_index = int(incoming_message) - 1
            demo_alert_id = "alert_demo_2025"
            simulation_result = await alert_service.simulate_action(demo_alert_id, action_index)
            polished_message = await watsonx_service.polish_simulation_message(
                simulation_result['simulation_message']
            )
            response_message = polished_message + "\n\nReply 'confirm' to schedule this action."

        elif incoming_message == "confirm":
            demo_alert_id = "alert_demo_2025"
            # For demo, assume last action was 0 (you can improve this with session tracking)
            success = await alert_service.confirm_action(demo_alert_id, 0)
            if success:
                response_message = (
                    "✅ Action confirmed.\n"
                    "We've scheduled 'Delay Vendor V204 by 2 days'.\n"
                    "We'll remind you again on 17 Aug."
                )
            else:
                response_message = "❌ Sorry, couldn't confirm the action. Please try again."

        else:
            response_message = (
                "👋 Welcome to Cash Flow Alerts!\n\n"
                "Send 'status' to check your cash flow, or wait for automated alerts when your balance needs attention."
            )

        twiml_response = whatsapp_service.create_response(response_message)
        return Response(content=twiml_response, media_type="application/xml")

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        error_response = whatsapp_service.create_response(
            "⚠️ Sorry, something went wrong. Please try again later."
        )
        return Response(content=error_response, media_type="application/xml")