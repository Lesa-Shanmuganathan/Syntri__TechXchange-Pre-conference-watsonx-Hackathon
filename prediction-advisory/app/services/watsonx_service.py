from ibm_watson_machine_learning import APIClient
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from typing import Dict, Any, Optional
import json
import logging
from app.config import settings
from app.database import get_sync_database

logger = logging.getLogger(__name__)

class WatsonxService:
    def __init__(self):
        self.db = get_sync_database()
        # Do NOT initialize self._client here

    def _get_client(self):
        """Create and return a new watsonx.ai client instance."""
        try:
            authenticator = IAMAuthenticator(settings.WATSONX_API_KEY)
            client = APIClient({
                'url': settings.WATSONX_URL,
                'authenticator': authenticator
            })
            client.set.default_project(settings.WATSONX_PROJECT_ID)
            logger.info("watsonx.ai client initialized successfully")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize watsonx client: {e}")
            return None

    async def polish_alert_message(self, raw_message: Dict[str, Any], alert_id: str) -> str:
        """Polish raw alert message using watsonx.ai"""
        # Check cache first
        cached = self.db.alerts.find_one({
            "alert_id": alert_id,
            "polished_message": {"$exists": True, "$ne": None}
        })
        if cached and cached.get('polished_message'):
            logger.info(f"Using cached polished message for {alert_id}")
            return cached['polished_message']

        # Generate new polished message
        client = self._get_client()
        if not client:
            return self._fallback_message(raw_message)

        try:
            polished = await self._generate_polished_message(raw_message, client)
            # Cache the result
            self.db.alerts.update_one(
                {"alert_id": alert_id},
                {"$set": {"polished_message": polished}}
            )
            return polished
        except Exception as e:
            logger.error(f"watsonx polishing failed: {e}")
            return self._fallback_message(raw_message)

    async def _generate_polished_message(self, raw_message: Dict[str, Any], client) -> str:
        """Generate polished message using watsonx.ai"""
        system_prompt = (
            "You are a financial assistant for small business owners. "
            "Create clear, action-oriented WhatsApp messages under 70 words. "
            "Use Indian Rupee (₹) symbol. Keep tone professional but friendly. "
            "Include numbered action options that users can tap to respond."
        )
        user_prompt = f"""
        Alert Details:
        - Date: {raw_message.get('alert_date', 'N/A')}
        - Cash will drop to ₹{raw_message.get('projected_balance', 0):,.0f} on {raw_message.get('breach_date', 'N/A')}
        - Threshold: ₹{raw_message.get('threshold', 0):,.0f}
        - Days to breach: {raw_message.get('days_to_breach', 'N/A')}

        Suggested Actions:
        1. {raw_message.get('actions', [{}])[0].get('description', '')}
        2. {raw_message.get('actions', [{}, {}])[1].get('description', '')}
        3. {raw_message.get('actions', [{}, {}, {}])[2].get('description', '')}

        Create a WhatsApp alert message with emoji, the problem, and 3 numbered action options.
        """

        model_params = {
            "decoding_method": "greedy",
            "max_new_tokens": 150,
            "temperature": 0.3,
            "top_p": 0.9
        }

        response = client.foundation_models.generate_text(
            model_id="ibm/granite-13b-instruct-v2",
            prompt=f"{system_prompt}\n\n{user_prompt}",
            params=model_params
        )
        return response['results'][0]['generated_text'].strip()

    def _fallback_message(self, raw_message: Dict[str, Any]) -> str:
        """Fallback message when watsonx is unavailable"""
        return (
            f"🚨 Cash Alert for {raw_message.get('alert_date', 'N/A')}\n"
            f"Your balance is projected to drop to ₹{raw_message.get('projected_balance', 0):,.0f}, "
            f"below the safe level of ₹{raw_message.get('threshold', 0):,.0f}.\n\n"
            "Suggested actions:\n"
            f"1️⃣ {raw_message.get('actions', [{}])[0].get('description', '')}\n"
            f"2️⃣ {raw_message.get('actions', [{}, {}])[1].get('description', '')}\n"
            f"3️⃣ {raw_message.get('actions', [{}, {}, {}])[2].get('description', '')}\n\n"
            "Reply with the number of your choice to simulate."
        )

    async def polish_simulation_message(self, simulation_data: Dict[str, Any]) -> str:
        """Polish simulation result message"""
        action = simulation_data.get('action_description', '')
        result = simulation_data.get('result', '')
        min_balance = simulation_data.get('min_balance', 0)

        if result == "resolved":
            return (
                f"📊 Simulation: {action} keeps your balance above ₹{min_balance:,.0f} through next week.\n"
                "Confirm this action? Reply 'confirm' to proceed."
            )
        else:
            return (
                f"📊 Simulation: {action} improves situation but balance still tight at ₹{min_balance:,.0f}.\n"
                "Consider combining with another action. Reply 'confirm' to proceed anyway."
            )
