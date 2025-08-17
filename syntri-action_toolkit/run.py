#!/usr/bin/env python3
"""
WhatsApp Agentic AI Application Runner
Handles initialization and startup
"""

import os
import sys
import logging
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def check_prerequisites():
    """Check if all prerequisites are met"""
    logger.info("🔍 Checking prerequisites...")
    
    issues = []
    
    # Check environment variables
    required_env_vars = [
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN',
        'EMAIL_USER',
        'EMAIL_PASSWORD'
    ]
    
    for var in required_env_vars:
        if not os.getenv(var):
            issues.append(f"Missing environment variable: {var}")
    
    # Check MongoDB connection
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv('MONGODB_URI', ''))
        client.server_info()
        logger.info("✅ MongoDB connection successful")
    except Exception as e:
        issues.append(f"MongoDB connection failed: {e}")
    
   

def initialize_services():
    """Initialize all services"""
    logger.info("🚀 Initializing services...")
    
    try:
        # Import after environment is loaded
        from app import app, agent
        
        # Test WatsonX service
        try:
            from watsonx_service import WatsonXService
            watsonx = WatsonXService()
            logger.info("✅ WatsonX service initialized")
        except Exception as e:
            logger.warning(f"⚠️  WatsonX service not available: {e}")
        
        # Test email service
        try:
            import smtplib
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASSWORD'))
            server.quit()
            logger.info("✅ Email service authenticated")
        except Exception as e:
            logger.error(f"❌ Email service failed: {e}")
        
        return app
        
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}")
        return None

def main():
    """Main application runner"""
    print("🤖 WhatsApp Agentic AI Solution")
    print("=" * 50)
    
    # Check prerequisites
    issues = check_prerequisites()
    
    if issues:
        logger.error("❌ Prerequisites check failed:")
        for issue in issues:
            logger.error(f"   - {issue}")
        logger.error("\n📋 Please fix the issues above and try again.")
        sys.exit(1)
    
    logger.info("✅ All prerequisites met")
    
    # Initialize services
    app = initialize_services()
    
    if not app:
        logger.error("❌ Failed to initialize services")
        sys.exit(1)
    
    # Print startup information
    print("\n🌟 Application ready!")
    print(f"📧 Demo email: {os.getenv('EMAIL_USER', 'Not configured')}")
    print(f"📱 Demo phone: +91xxxxxxxxxx")
    print(f"🔗 Health check: http://localhost:8000/health")
    print(f"🧪 Demo endpoint: http://localhost:8000/demo")
    print("\n📱 WhatsApp Commands:")
    print("   • Send 'hi' or 'status' to see pending actions")
    print("   • Send 'payment_reminder' to send payment reminder")
    print("   • Send 'reorder_alert' to send reorder alert")
    print("   • Send 'upi_pay' to generate UPI payment link")
    print("\n🔧 Setup webhook URL in Twilio Console:")
    print("   • Use ngrok: ngrok http 8000")
    print("   • Set webhook: https://your-ngrok-url.ngrok.io/webhook")
    print("\n" + "=" * 50)
    
    # Start the Flask application
    try:
        logger.info("🚀 Starting Flask application...")
        app.run(
            host='0.0.0.0', 
            port=int(os.getenv('PORT', 8000)), 
            debug=os.getenv('FLASK_ENV') == 'development'
        )
    except KeyboardInterrupt:
        logger.info("👋 Application stopped by user")
    except Exception as e:
        logger.error(f"❌ Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
