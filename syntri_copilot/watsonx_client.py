# watsonx_client.py
import os
import json
import requests
from dotenv import load_dotenv
import time

load_dotenv()

# Environment variables
WATSONX_API_KEY = os.getenv("WATSONX_APIKEY")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID")
WATSONX_MODEL_ID = os.getenv("WATSONX_MODEL_ID", "ibm/granite-3-3-8b-instruct")
WATSONX_REGION = os.getenv("WATSONX_REGION", "us-south")

# Correct Watsonx URLs based on region
WATSONX_URLS = {
    "us-south": "https://us-south.ml.cloud.ibm.com/ml/v1/text/generation",
    "eu-gb": "https://eu-gb.ml.cloud.ibm.com/ml/v1/text/generation",
    "jp-tok": "https://jp-tok.ml.cloud.ibm.com/ml/v1/text/generation",
    "eu-de": "https://eu-de.ml.cloud.ibm.com/ml/v1/text/generation"
}

WATSONX_AUTH_URL = f"https://iam.cloud.ibm.com/identity/token"
TIMEOUT = 30  # seconds

# Cache for access token
_access_token_cache = {
    "token": None,
    "expires_at": 0
}

def get_access_token() -> str:
    """
    Get IBM Cloud IAM access token for Watsonx authentication.
    Implements token caching to avoid repeated authentication calls.
    """
    current_time = time.time()
    
    # Return cached token if still valid (with 5-minute buffer)
    if (_access_token_cache["token"] and 
        current_time < (_access_token_cache["expires_at"] - 300)):
        return _access_token_cache["token"]
    
    if not WATSONX_API_KEY:
        raise ValueError("WATSONX_APIKEY environment variable not set")
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    
    data = {
        "grant_type": "urn:iam:params:oauth:grant-type:apikey",
        "apikey": WATSONX_API_KEY
    }
    
    try:
        response = requests.post(
            WATSONX_AUTH_URL,
            headers=headers,
            data=data,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
        
        if not access_token:
            raise ValueError("No access token in response")
        
        # Cache the token
        _access_token_cache["token"] = access_token
        _access_token_cache["expires_at"] = current_time + expires_in
        
        print("✅ Successfully obtained Watsonx access token")
        return access_token
        
    except requests.RequestException as e:
        print(f"❌ Failed to get Watsonx access token: {e}")
        raise
    except (KeyError, ValueError) as e:
        print(f"❌ Invalid token response: {e}")
        raise

def test_watsonx_connection() -> bool:
    """
    Test the Watsonx connection and configuration.
    """
    try:
        token = get_access_token()
        return bool(token)
    except Exception as e:
        print(f"❌ Watsonx connection test failed: {e}")
        return False

def polish_text(raw_text: str) -> str:
    """
    Enhanced text polishing using IBM Watsonx with proper authentication and error handling.
    Falls back to raw text if Watsonx is unavailable.
    """
    # Quick validation
    if not raw_text or not raw_text.strip():
        return raw_text
    
    # Check if Watsonx is configured
    if not WATSONX_API_KEY or not WATSONX_PROJECT_ID:
        print("⚠️ Watsonx not configured - returning raw text")
        return raw_text
    
    # Get the correct API URL
    api_url = WATSONX_URLS.get(WATSONX_REGION)
    if not api_url:
        print(f"❌ Invalid Watsonx region: {WATSONX_REGION}")
        return raw_text
    
    try:
        # Get access token
        access_token = get_access_token()
        
        # Prepare the request
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Enhanced prompt for better business communication
        prompt = f"""Polish this business message for WhatsApp. Make it friendly, clear, and professional while keeping it concise:

Original: {raw_text}

Polished version:"""
        
        payload = {
            "model_id": WATSONX_MODEL_ID,
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": 200,
                "min_new_tokens": 10,
                "stop_sequences": ["\n\n", "Original:", "Polished version:", "Note:"],
                "repetition_penalty": 1.1,
                "temperature": 0.3
            },
            "project_id": WATSONX_PROJECT_ID
        }
        
        print(f"🔄 Polishing text with Watsonx: {raw_text[:50]}...")
        
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        
        if "results" in data and data["results"]:
            result = data["results"][0]
            generated_text = result.get("generated_text", "").strip()
            
            if generated_text and len(generated_text) > 10:
                # Clean up the generated text
                polished = clean_generated_text(generated_text, raw_text)
                print(f"✅ Text polished successfully: {polished[:50]}...")
                return polished
            else:
                print("⚠️ Generated text too short, using original")
                return raw_text
        else:
            print(f"⚠️ Unexpected response format: {data}")
            return raw_text
            
    except requests.exceptions.Timeout:
        print("⏱️ Watsonx request timeout - using raw text")
        return raw_text
    except requests.exceptions.HTTPError as e:
        print(f"❌ Watsonx HTTP error: {e}")
        if e.response.status_code == 401:
            print("🔑 Authentication failed - check your API key")
        elif e.response.status_code == 403:
            print("🚫 Access denied - check your project permissions")
        elif e.response.status_code == 404:
            print("🔍 Resource not found - check your model ID and region")
        return raw_text
    except Exception as e:
        print(f"❌ Unexpected Watsonx error: {e}")
        return raw_text

def clean_generated_text(generated_text: str, original_text: str) -> str:
    """
    Clean and validate the generated text from Watsonx.
    """
    if not generated_text:
        return original_text
    
    # Remove common artifacts
    cleaned = generated_text.strip()
    
    # Remove repetitive patterns
    lines = cleaned.split('\n')
    unique_lines = []
    for line in lines:
        line = line.strip()
        if line and line not in unique_lines:
            unique_lines.append(line)
    
    cleaned = '\n'.join(unique_lines)
    
    # If the result is too short or doesn't make sense, return original
    if len(cleaned) < len(original_text) * 0.5:
        return original_text
    
    # If it's too long, truncate appropriately
    if len(cleaned) > 1500:  # WhatsApp limit consideration
        sentences = cleaned.split('. ')
        truncated = []
        current_length = 0
        
        for sentence in sentences:
            if current_length + len(sentence) > 1400:
                break
            truncated.append(sentence)
            current_length += len(sentence) + 2
        
        cleaned = '. '.join(truncated)
        if not cleaned.endswith('.'):
            cleaned += '.'
    
    return cleaned

def get_watsonx_status() -> dict:
    """
    Get current Watsonx configuration status.
    """
    status = {
        "configured": bool(WATSONX_API_KEY and WATSONX_PROJECT_ID),
        "api_key_set": bool(WATSONX_API_KEY),
        "project_id_set": bool(WATSONX_PROJECT_ID),
        "model_id": WATSONX_MODEL_ID,
        "region": WATSONX_REGION,
        "api_url": WATSONX_URLS.get(WATSONX_REGION),
        "connection_tested": False
    }
    
    if status["configured"]:
        try:
            status["connection_tested"] = test_watsonx_connection()
        except Exception as e:
            status["connection_error"] = str(e)
    
    return status

# Fallback polishing function using simple rules
def simple_polish_text(raw_text: str) -> str:
    """
    Simple text polishing without AI - adds emojis and formats nicely.
    """
    if not raw_text:
        return raw_text
    
    text = raw_text.strip()
    
    # Add appropriate emojis based on content
    if "week" in text.lower() and any(word in text.lower() for word in ["sales", "expenses", "net"]):
        if not text.startswith("📊"):
            text = "📊 " + text
    
    if "₹" in text:
        # Format numbers with proper spacing
        import re
        text = re.sub(r'₹(\d+)', r'₹\1', text)
    
    # Capitalize first letter if needed
    if text and not text[0].isupper() and not text.startswith(("📊", "💰", "📈", "📉", "✅", "❌")):
        text = text[0].upper() + text[1:]
    
    return text

# Override polish_text to use simple version if Watsonx fails
def polish_text_with_fallback(raw_text: str) -> str:
    """
    Try Watsonx polishing, fall back to simple polishing if it fails.
    """
    if not WATSONX_API_KEY or not WATSONX_PROJECT_ID:
        return simple_polish_text(raw_text)
    
    try:
        # Try Watsonx first
        polished = polish_text(raw_text)
        
        # If Watsonx returned the same text (likely failed), use simple polish
        if polished == raw_text:
            return simple_polish_text(raw_text)
        
        return polished
    except Exception:
        return simple_polish_text(raw_text)