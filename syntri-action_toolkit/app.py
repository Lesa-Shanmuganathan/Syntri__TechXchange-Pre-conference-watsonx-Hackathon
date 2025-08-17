"""
WhatsApp Agentic AI Solution
Main Flask application for handling WhatsApp interactions via Twilio
"""

from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os
import json
import logging
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pymongo import MongoClient
from bson import ObjectId
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
class Config:
    # Twilio Configuration
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', 'your_twilio_account_sid')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', 'your_twilio_auth_token')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', 'whatsapp:+14155238886')
    
    # WatsonX Configuration
    WATSONX_API_KEY = os.getenv('WATSONX_API_KEY', 'your_watsonx_api_key')
    WATSONX_PROJECT_ID = os.getenv('WATSONX_PROJECT_ID', 'your_project_id')
    WATSONX_URL = os.getenv('WATSONX_URL', 'https://us-south.ml.cloud.ibm.com')
    
    # Email Configuration (using Gmail SMTP)
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USER = os.getenv('EMAIL_USER', 'your_email@gmail.com')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'your_app_password')
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/syntri')
    
    # Demo contact for output visibility
    DEMO_EMAIL = 'lesa38835656@gmail.com'

# Initialize services
twilio_client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
mongo_client = MongoClient(Config.MONGODB_URI)
db = mongo_client.syntri

class WhatsAppAgent:
    def __init__(self):
        self.setup_demo_data()
    
    def setup_demo_data(self):
        """Initialize demo data in MongoDB collections"""
        try:
            # Clear existing demo data
            db.action_tasks.delete_many({"demo": True})
            db.financial_records.delete_many({"demo": True})
            
            # Insert demo action tasks
            demo_tasks = [
                {
                    "task_type": "reorder",
                    "description": "Reorder Item X - Raw Materials",
                    "vendor_email": Config.DEMO_EMAIL,
                    "vendor_phone": "+919500352059",
                    "priority": "high",
                    "status": "pending",
                    "created_date": datetime.now(),
                    "due_date": datetime.now() + timedelta(days=2),
                    "demo": True
                },
                {
                    "task_type": "followup",
                    "description": "Follow-up call with Supplier Y",
                    "vendor_email": Config.DEMO_EMAIL,
                    "priority": "medium",
                    "status": "pending",
                    "created_date": datetime.now(),
                    "due_date": datetime.now() + timedelta(days=1),
                    "demo": True
                }
            ]
            
            # Insert demo financial records
            demo_payments = [
                {
                    "transaction_type": "payable",
                    "supplier_name": "Vendor Z",
                    "supplier_email": Config.DEMO_EMAIL,
                    "amount": 15000,
                    "due_date": datetime.now() + timedelta(days=3),
                    "status": "pending",
                    "invoice_number": "INV-001",
                    "demo": True
                },
                {
                    "transaction_type": "payable",
                    "supplier_name": "Supplier ABC",
                    "supplier_email": Config.DEMO_EMAIL,
                    "amount": 8500,
                    "due_date": datetime.now() + timedelta(days=7),
                    "status": "pending",
                    "invoice_number": "INV-002",
                    "demo": True
                }
            ]
            
            db.action_tasks.insert_many(demo_tasks)
            db.financial_records.insert_many(demo_payments)
            
            logger.info("Demo data initialized successfully")
            
        except Exception as e:
            logger.error(f"Error setting up demo data: {e}")
    
    def send_email_reminder(self, to_email, subject, message):
        """Send email reminder to supplier/vendor"""
        try:
            msg = MIMEMultipart()
            msg['From'] = Config.EMAIL_USER
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'html'))
            
            server = smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT)
            server.starttls()
            server.login(Config.EMAIL_USER, Config.EMAIL_PASSWORD)
            
            text = msg.as_string()
            server.sendmail(Config.EMAIL_USER, to_email, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    def get_pending_actions(self):
        """Get pending actions from database"""
        try:
            pending_payments = list(db.financial_records.find({"status": "pending", "demo": True}).limit(3))
            pending_tasks = list(db.action_tasks.find({"status": "pending", "demo": True}).limit(3))
            
            actions = []
            for payment in pending_payments:
                actions.append({
                    "type": "payment",
                    "description": f"Payment to {payment['supplier_name']}",
                    "amount": payment.get('amount', 0),
                    "due_date": payment.get('due_date')
                })
            
            for task in pending_tasks:
                actions.append({
                    "type": task['task_type'],
                    "description": task['description'],
                    "priority": task.get('priority', 'medium')
                })
            
            return actions
            
        except Exception as e:
            logger.error(f"Error getting pending actions: {e}")
            return []
    
    def handle_payment_reminder(self):
        """Handle payment reminder button click"""
        try:
            # Get pending payment
            payment = db.financial_records.find_one({"status": "pending", "demo": True})
            
            if not payment:
                return "No pending payments found."
            
            # Send email reminder
            subject = f"Payment Reminder - Invoice {payment['invoice_number']}"
            message = f"""
            <html>
            <body>
                <h3>Payment Reminder</h3>
                <p>Dear {payment['supplier_name']},</p>
                <p>This is a friendly reminder about the pending payment:</p>
                <ul>
                    <li><strong>Invoice:</strong> {payment['invoice_number']}</li>
                    <li><strong>Amount:</strong> ₹{payment['amount']}</li>
                    <li><strong>Due Date:</strong> {payment['due_date'].strftime('%Y-%m-%d')}</li>
                </ul>
                <p>Please process the payment at your earliest convenience.</p>
                <p>Best regards,<br>Business Team</p>
            </body>
            </html>
            """
            
            success = self.send_email_reminder(payment['supplier_email'], subject, message)
            
            if success:
                # Update database
                db.financial_records.update_one(
                    {"_id": payment["_id"]},
                    {"$set": {"last_reminder": datetime.now()}}
                )
                
                return f"✅ Payment reminder sent to {payment['supplier_name']} at {payment['supplier_email']}"
            else:
                return "❌ Failed to send payment reminder. Please try again."
                
        except Exception as e:
            logger.error(f"Error handling payment reminder: {e}")
            return "❌ Error processing payment reminder."
    
    def handle_reorder_alert(self):
        """Handle reorder alert button click"""
        try:
            # Get pending reorder task
            task = db.action_tasks.find_one({"task_type": "reorder", "status": "pending", "demo": True})
            
            if not task:
                return "No pending reorder items found."
            
            # Send email alert
            subject = f"Reorder Alert - {task['description']}"
            message = f"""
            <html>
            <body>
                <h3>Reorder Alert</h3>
                <p>Dear Vendor,</p>
                <p>We need to reorder the following item:</p>
                <ul>
                    <li><strong>Item:</strong> {task['description']}</li>
                    <li><strong>Priority:</strong> {task['priority'].upper()}</li>
                    <li><strong>Required by:</strong> {task['due_date'].strftime('%Y-%m-%d')}</li>
                </ul>
                <p>Please confirm availability and provide quotation.</p>
                <p>Best regards,<br>Procurement Team</p>
            </body>
            </html>
            """
            
            success = self.send_email_reminder(task['vendor_email'], subject, message)
            
            if success:
                # Update database
                db.action_tasks.update_one(
                    {"_id": task["_id"]},
                    {"$set": {"alert_sent": datetime.now()}}
                )
                
                return f"✅ Reorder alert sent to vendor at {task['vendor_email']}"
            else:
                return "❌ Failed to send reorder alert. Please try again."
                
        except Exception as e:
            logger.error(f"Error handling reorder alert: {e}")
            return "❌ Error processing reorder alert."
    
    def handle_upi_payment(self):
        """Handle UPI payment button click (simulated)"""
        try:
            # Get pending payment
            payment = db.financial_records.find_one({"status": "pending", "demo": True})
            
            if not payment:
                return "No pending payments found."
            
            # Generate simulated UPI link
            upi_id = "business@paytm"
            amount = payment['amount']
            note = f"Payment for {payment['invoice_number']}"
            
            upi_link = f"upi://pay?pa={upi_id}&pn=Business&am={amount}&cu=INR&tn={note}"
            
            # Update database to simulate payment initiation
            db.financial_records.update_one(
                {"_id": payment["_id"]},
                {"$set": {"payment_initiated": datetime.now()}}
            )
            
            return f"💳 UPI Payment Link Generated!\n\nAmount: ₹{amount}\nInvoice: {payment['invoice_number']}\n\n🔗 Link: {upi_link}\n\n*This is a simulated payment link for demo purposes*"
            
        except Exception as e:
            logger.error(f"Error handling UPI payment: {e}")
            return "❌ Error generating UPI payment link."
    
    def create_action_buttons(self):
        """Create WhatsApp interactive buttons"""
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": "Choose an action:"
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "payment_reminder",
                                "title": "Send Payment Reminder"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "reorder_alert",
                                "title": "Set Reorder Alert"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "upi_pay",
                                "title": "UPI Pay Now"
                            }
                        }
                    ]
                }
            }
        }

# Initialize agent
agent = WhatsAppAgent()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    try:
        # Get message data
        message_body = request.values.get('Body', '').lower().strip()
        from_number = request.values.get('From', '')
        
        logger.info(f"Received message: {message_body} from {from_number}")
        
        response = MessagingResponse()
        msg = response.message()
        
        # Check for button responses
        if message_body == "payment_reminder":
            result = agent.handle_payment_reminder()
            msg.body(result)
            
        elif message_body == "reorder_alert":
            result = agent.handle_reorder_alert()
            msg.body(result)
            
        elif message_body == "upi_pay":
            result = agent.handle_upi_payment()
            msg.body(result)
            
        # Handle initial greeting or status request
        elif any(word in message_body for word in ['hi', 'hello', 'status', 'pending', 'actions']):
            pending_actions = agent.get_pending_actions()
            
            if pending_actions:
                actions_text = f"📋 You have {len(pending_actions)} pending actions today:\n\n"
                for i, action in enumerate(pending_actions, 1):
                    actions_text += f"{i}. {action['description']}\n"
                
                actions_text += "\n🔽 Choose an action below:"
                msg.body(actions_text)
                
                # Send interactive buttons (Note: Basic Twilio sandbox might not support interactive buttons)
                # For demo purposes, we'll use simple text options
                msg.body("\nReply with:\n• 'payment_reminder' - Send Payment Reminder\n• 'reorder_alert' - Set Reorder Alert\n• 'upi_pay' - UPI Pay Now")
            else:
                msg.body("✅ No pending actions found. All tasks are up to date!")
        
        else:
            msg.body("👋 Welcome to Business Agent!\n\nSend 'status' to see pending actions, or use these commands:\n• payment_reminder\n• reorder_alert\n• upi_pay")
        
        return str(response)
        
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        response = MessagingResponse()
        msg = response.message()
        msg.body("❌ Sorry, there was an error processing your request. Please try again.")
        return str(response)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "mongodb": "connected" if mongo_client else "disconnected",
            "twilio": "configured" if Config.TWILIO_ACCOUNT_SID else "not configured"
        }
    })

@app.route('/demo', methods=['GET'])
def demo_endpoint():
    """Demo endpoint to test functionality"""
    try:
        # Test database connection
        pending_actions = agent.get_pending_actions()
        
        return jsonify({
            "message": "Demo endpoint working",
            "pending_actions": len(pending_actions),
            "actions": [action['description'] for action in pending_actions[:3]],
            "database_status": "connected"
        })
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "database_status": "error"
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
