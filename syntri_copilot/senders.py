# senders.py
import os
import time
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

load_dotenv()

TW_SID = os.getenv("TWILIO_ACCOUNT_SID")
TW_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TW_FROM = os.getenv("TWILIO_WHATSAPP_NUMBER")  # e.g. whatsapp:+14155238886

# Initialize Twilio client with better error handling
tw_client = None
if TW_SID and TW_TOKEN:
    try:
        tw_client = Client(TW_SID, TW_TOKEN)
        # Test the connection
        account = tw_client.api.account.fetch()
        print(f"✅ Twilio connected successfully. Account: {account.friendly_name}")
    except Exception as e:
        print(f"❌ Twilio initialization error: {e}")
        tw_client = None
else:
    print("⚠️ Twilio credentials not found. Running in development mode.")

def send_whatsapp(to_number: str, body: str, max_retries: int = 3) -> str:
    """
    Send WhatsApp message with retry logic and better error handling.
    
    Args:
        to_number: Recipient phone number (e.g., 'whatsapp:+919500352059')
        body: Message content
        max_retries: Maximum number of retry attempts
    
    Returns:
        Message SID if successful, None if failed
    """
    if not tw_client or not TW_FROM:
        # Development fallback
        print(f"🔧 [DEV MODE] Would send to {to_number}:")
        print(f"📄 Message: {body}")
        print("---")
        return "dev_mode_message_id"
    
    # Ensure proper WhatsApp format
    if not to_number.startswith('whatsapp:'):
        print(f"⚠️ Invalid WhatsApp number format: {to_number}")
        return None
    
    # Validate message content
    if not body or len(body.strip()) == 0:
        print("⚠️ Empty message body, skipping send")
        return None
    
    # Truncate long messages
    if len(body) > 1600:  # WhatsApp limit is ~1600 chars
        body = body[:1590] + "..."
        print("✂️ Message truncated to fit WhatsApp limits")
    
    for attempt in range(max_retries):
        try:
            message = tw_client.messages.create(
                body=body,
                from_=TW_FROM,
                to=to_number
            )
            
            print(f"✅ WhatsApp message sent successfully!")
            print(f"📱 To: {to_number}")
            print(f"🆔 SID: {message.sid}")
            print(f"📊 Status: {message.status}")
            
            return message.sid
            
        except TwilioException as e:
            print(f"❌ Twilio error (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Handle specific Twilio errors
            if e.code == 20003:  # Authentication error
                print("🔑 Authentication failed. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
                break
            elif e.code == 21211:  # Invalid 'To' phone number
                print("📞 Invalid phone number format")
                break
            elif e.code == 21610:  # Message exceeds character limit
                print("📝 Message too long")
                break
            elif e.code in [21617, 21618]:  # WhatsApp number not enabled
                print("📱 WhatsApp not enabled for this number")
                break
            elif e.code == 21614:  # 'To' number is not a valid mobile number
                print("📱 Not a valid mobile number for WhatsApp")
                break
            
            # Rate limiting - wait and retry
            if e.code == 20429:
                wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                print(f"⏱️ Rate limited, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
            
            # For other errors, wait a bit before retrying
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 5)
                print(f"⏱️ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        except Exception as e:
            print(f"❌ Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 5)
                print(f"⏱️ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
    
    print(f"❌ Failed to send message after {max_retries} attempts")
    return None

def validate_whatsapp_number(number: str) -> bool:
    """
    Validate WhatsApp number format.
    
    Args:
        number: Phone number to validate
    
    Returns:
        True if valid format, False otherwise
    """
    if not number:
        return False
    
    # Must start with 'whatsapp:'
    if not number.startswith('whatsapp:'):
        return False
    
    # Extract the phone number part
    phone_part = number[9:]  # Remove 'whatsapp:' prefix
    
    # Must start with '+'
    if not phone_part.startswith('+'):
        return False
    
    # Must have at least 10 digits after the '+'
    digits = phone_part[1:]  # Remove '+' prefix
    if len(digits) < 10 or not digits.isdigit():
        return False
    
    return True

def format_whatsapp_number(number: str) -> str:
    """
    Format a phone number for WhatsApp usage.
    
    Args:
        number: Phone number (various formats accepted)
    
    Returns:
        Properly formatted WhatsApp number or None if invalid
    """
    if not number:
        return None
    
    # Already in correct format
    if number.startswith('whatsapp:+'):
        return number if validate_whatsapp_number(number) else None
    
    # Remove any non-digit characters except '+'
    cleaned = ''.join(c for c in number if c.isdigit() or c == '+')
    
    # Add '+' if missing
    if not cleaned.startswith('+'):
        # Assume it's an Indian number if it starts with 91
        if cleaned.startswith('91') and len(cleaned) == 12:
            cleaned = '+' + cleaned
        # Assume it's an Indian number if it's 10 digits
        elif len(cleaned) == 10:
            cleaned = '+91' + cleaned
        else:
            return None
    
    # Format as WhatsApp number
    whatsapp_number = f'whatsapp:{cleaned}'
    
    return whatsapp_number if validate_whatsapp_number(whatsapp_number) else None

def send_whatsapp_safe(to_number: str, body: str) -> bool:
    """
    Safe wrapper for sending WhatsApp messages with validation.
    
    Args:
        to_number: Recipient phone number
        body: Message content
    
    Returns:
        True if message sent successfully, False otherwise
    """
    # Format the number
    formatted_number = format_whatsapp_number(to_number)
    if not formatted_number:
        print(f"❌ Invalid phone number format: {to_number}")
        return False
    
    # Send the message
    message_sid = send_whatsapp(formatted_number, body)
    return message_sid is not None

def get_twilio_status() -> dict:
    """
    Get the current status of Twilio configuration.
    
    Returns:
        Dictionary with configuration status
    """
    status = {
        "configured": tw_client is not None,
        "account_sid": TW_SID[:10] + "..." if TW_SID else None,
        "from_number": TW_FROM,
        "client_ready": False
    }
    
    if tw_client:
        try:
            account = tw_client.api.account.fetch()
            status["client_ready"] = True
            status["account_name"] = getattr(account, 'friendly_name', 'Unknown')
            status["account_status"] = getattr(account, 'status', 'Unknown')
        except Exception as e:
            status["error"] = str(e)
    
    return status