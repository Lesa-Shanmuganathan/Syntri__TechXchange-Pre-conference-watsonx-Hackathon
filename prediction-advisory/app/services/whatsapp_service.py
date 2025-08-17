from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    async def send_alert(self, message: str, to_number: str) -> bool:
        """Send alert message via WhatsApp"""
        try:
            message = self.client.messages.create(
                body=message,
                from_=settings.TWILIO_WHATSAPP_NUMBER,
                to=f"whatsapp:{to_number}"
            )
            logger.info(f"Alert sent successfully: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False
    
    def create_response(self, message: str) -> str:
        """Create TwiML response for webhook"""
        resp = MessagingResponse()
        resp.message(message)
        return str(resp)