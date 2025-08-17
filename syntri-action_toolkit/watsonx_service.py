"""
WatsonX Integration Service
LLM usage for message personalization and intent detection
"""

import os
import logging
from ibm_watson_machine_learning import APIClient
import json

logger = logging.getLogger(__name__)

class WatsonXService:
    def __init__(self):
        self.api_key = os.getenv('WATSONX_API_KEY')
        self.project_id = os.getenv('WATSONX_PROJECT_ID')
        self.url = os.getenv('WATSONX_URL', 'https://us-south.ml.cloud.ibm.com')
        
        self.client = None
        self.model_id = "ibm/granite-3-3-8b-instruct"
        
        if self.api_key and self.project_id:
            try:
                # Initialize Watson ML client
                wml_credentials = {
                    "url": self.url,
                    "apikey": self.api_key
                }
                
                self.client = APIClient(wml_credentials)
                self.client.set.default_project(self.project_id)
                logger.info("WatsonX service initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize WatsonX: {e}")
                self.client = None
        else:
            logger.warning("WatsonX credentials not provided, using fallback responses")
    
    def personalize_message(self, template_type, context):
        """
        Personalize message templates using LLM calls  """
        if not self.client:
            return self._get_fallback_template(template_type, context)
        
        try:
            prompt = self._build_personalization_prompt(template_type, context)
            
            # Use minimal parameters for cost efficiency
            parameters = {
                "decoding_method": "greedy",
                "max_new_tokens": 150,
                "temperature": 0.1,
                "stop_sequences": ["\n\n"]
            }
            
            result = self.client.foundation_model.generate_text(
                prompt=prompt,
                model_id=self.model_id,
                parameters=parameters
            )
            
            if result and 'results' in result:
                personalized_text = result['results'][0]['generated_text'].strip()
                logger.info(f"Generated personalized message for {template_type}")
                return personalized_text
            else:
                return self._get_fallback_template(template_type, context)
                
        except Exception as e:
            logger.error(f"Error personalizing message: {e}")
            return self._get_fallback_template(template_type, context)
    
    def detect_intent(self, message):
        """
        Detect user intent from message (minimal usage)
        Returns: greeting, status_check, action_request, unknown
        """
        if not self.client:
            return self._simple_intent_detection(message)
        
        try:
            prompt = f"""
            Classify the user intent for this WhatsApp business message. 
            Message: "{message}"
            
            Possible intents:
            - greeting: hi, hello, start conversation
            - status_check: asking about pending tasks, actions, status
            - action_request: wants to perform specific action
            - unknown: unclear or unrelated message
            
            Intent:"""
            
            parameters = {
                "decoding_method": "greedy",
                "max_new_tokens": 20,
                "temperature": 0.1
            }
            
            result = self.client.foundation_model.generate_text(
                prompt=prompt,
                model_id=self.model_id,
                parameters=parameters
            )
            
            if result and 'results' in result:
                intent = result['results'][0]['generated_text'].strip().lower()
                logger.info(f"Detected intent: {intent} for message: {message[:50]}")
                return intent
            else:
                return self._simple_intent_detection(message)
                
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            return self._simple_intent_detection(message)
    
    def _build_personalization_prompt(self, template_type, context):
        """Build prompt for message personalization"""
        base_prompts = {
            "payment_reminder": f"""
            Create a professional payment reminder email for:
            Company: {context.get('company_name', 'Valued Partner')}
            Amount: ₹{context.get('amount', '0')}
            Invoice: {context.get('invoice_number', 'N/A')}
            Due Date: {context.get('due_date', 'ASAP')}
            
            Make it polite but firm. Include all details.
            
            Email body:""",
            
            "reorder_alert": f"""
            Create a professional reorder request email for:
            Item: {context.get('item_description', 'Product')}
            Priority: {context.get('priority', 'Medium')}
            Required by: {context.get('due_date', 'Soon')}
            
            Make it clear and actionable.
            
            Email body:""",
            
            "followup": f"""
            Create a professional follow-up message for:
            Topic: {context.get('topic', 'Previous Discussion')}
            Contact: {context.get('contact_name', 'Partner')}
            
            Keep it brief and purposeful.
            
            Message:"""
        }
        
        return base_prompts.get(template_type, "Create a professional business message.")
    
    def _get_fallback_template(self, template_type, context):
        """Fallback templates when WatsonX is unavailable"""
        templates = {
            "payment_reminder": f"""
Dear {context.get('company_name', 'Valued Partner')},

This is a friendly reminder about the pending payment:

Invoice Number: {context.get('invoice_number', 'N/A')}
Amount: ₹{context.get('amount', '0')}
Due Date: {context.get('due_date', 'ASAP')}

Please process the payment at your earliest convenience.

Best regards,
Business Team
            """,
            
            "reorder_alert": f"""
Dear Vendor,

We need to reorder the following item:

Item: {context.get('item_description', 'Product')}
Priority: {context.get('priority', 'Medium')}
Required by: {context.get('due_date', 'Soon')}

Please confirm availability and provide quotation.

Best regards,
Procurement Team
            """,
            
            "followup": f"""
Dear {context.get('contact_name', 'Partner')},

Following up on our previous discussion regarding {context.get('topic', 'business matters')}.

Please let us know the current status.

Best regards,
Business Team
            """
        }
        
        return templates.get(template_type, "Thank you for your business.")
    
    def _simple_intent_detection(self, message):
        """Simple rule-based intent detection as fallback"""
        message = message.lower()
        
        if any(word in message for word in ['hi', 'hello', 'hey', 'start']):
            return 'greeting'
        elif any(word in message for word in ['status', 'pending', 'actions', 'tasks']):
            return 'status_check'
        elif any(word in message for word in ['payment', 'remind', 'reorder', 'alert', 'pay']):
            return 'action_request'
        else:

            return 'unknown'
