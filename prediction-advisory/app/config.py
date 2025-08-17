from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "syntri"
    
    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"
    
    # watsonx.ai
    WATSONX_API_KEY: str
    WATSONX_PROJECT_ID: str
    WATSONX_URL: str = "https://us-south.ml.cloud.ibm.com"
    
    # App Config
    CASH_MIN_THRESHOLD: float = 5000.0
    FORECAST_DAYS: int = 7
    
    class Config:
        env_file = ".env"

settings = Settings()