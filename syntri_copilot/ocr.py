# ocr.py
import os
import requests
from io import BytesIO
from PIL import Image
import pytesseract
import numpy as np
import cv2
from dotenv import load_dotenv

load_dotenv()

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

def download_media(url: str) -> bytes:
    """
    Download media from Twilio with proper authentication.
    """
    if not TWILIO_SID or not TWILIO_TOKEN:
        raise ValueError("Twilio credentials not found in environment variables")
    
    try:
        # Twilio media URLs require HTTP Basic Auth
        response = requests.get(
            url, 
            auth=(TWILIO_SID, TWILIO_TOKEN), 
            timeout=30,
            headers={'User-Agent': 'Syntri-WhatsApp-Bot/1.0'}
        )
        response.raise_for_status()
        
        if len(response.content) == 0:
            raise ValueError("Downloaded media file is empty")
            
        print(f"✅ Downloaded media: {len(response.content)} bytes")
        return response.content
        
    except requests.exceptions.Timeout:
        raise Exception("Timeout while downloading media from Twilio")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to download media: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error downloading media: {str(e)}")

def preprocess_for_ocr(pil_image: Image.Image) -> np.ndarray:
    """
    Preprocess image for better OCR results.
    """
    try:
        # Convert to RGB if not already
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Convert PIL to numpy array
        img_array = np.array(pil_image)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Apply adaptive thresholding for better contrast
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Optional: Apply morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
        
    except Exception as e:
        print(f"⚠️ Preprocessing failed: {e}, using original image")
        # Fallback to simple grayscale conversion
        return cv2.cvtColor(np.array(pil_image.convert('RGB')), cv2.COLOR_RGB2GRAY)

def image_bytes_to_text(image_bytes: bytes) -> str:
    """
    Extract text from image bytes using OCR.
    """
    if not image_bytes:
        raise ValueError("Image bytes is empty")
    
    try:
        # Open image from bytes
        pil_image = Image.open(BytesIO(image_bytes))
        
        # Check if image is valid
        pil_image.verify()
        
        # Reopen image (verify() closes it)
        pil_image = Image.open(BytesIO(image_bytes))
        
        print(f"📷 Processing image: {pil_image.size}, mode: {pil_image.mode}")
        
        # Preprocess image
        processed_img = preprocess_for_ocr(pil_image)
        
        # Try OCR with different configurations
        ocr_configs = [
            '--psm 6',  # Uniform block of text
            '--psm 4',  # Single column of text
            '--psm 3',  # Fully automatic page segmentation
            '--psm 11', # Sparse text
        ]
        
        best_text = ""
        max_confidence = 0
        
        for config in ocr_configs:
            try:
                # Get text with confidence scores
                data = pytesseract.image_to_data(
                    processed_img, 
                    lang='eng',
                    config=config,
                    output_type=pytesseract.Output.DICT
                )
                
                # Calculate average confidence
                confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)
                    
                    if avg_confidence > max_confidence:
                        max_confidence = avg_confidence
                        text = pytesseract.image_to_string(
                            processed_img, 
                            lang='eng',
                            config=config
                        )
                        best_text = text.strip()
                        
            except Exception as e:
                print(f"⚠️ OCR config {config} failed: {e}")
                continue
        
        # Fallback to simple OCR if no good result
        if not best_text or max_confidence < 30:
            print("🔄 Using fallback OCR method")
            try:
                best_text = pytesseract.image_to_string(
                    processed_img, 
                    lang='eng'
                ).strip()
            except Exception as e:
                print(f"❌ Fallback OCR also failed: {e}")
                best_text = ""
        
        print(f"📝 OCR Result (confidence: {max_confidence:.1f}%): {best_text[:100]}...")
        
        if not best_text:
            raise ValueError("No text could be extracted from the image")
            
        return best_text
        
    except Exception as e:
        raise Exception(f"OCR processing failed: {str(e)}")

def validate_image(image_bytes: bytes) -> bool:
    """
    Validate if the image bytes represent a valid image.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()
        return True
    except Exception:
        return False