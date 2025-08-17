# main.py
import os
import traceback
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import Response
from datetime import datetime
from db import db, financial_records, conversations, media_inputs
from parser import parse_text_message, extract_amount_from_query
from ocr import download_media, image_bytes_to_text, validate_image
from senders import send_whatsapp
from forecast import (
    compute_weekly_insights, simulate_hire, simulate_sales_change, 
    compute_monthly_totals, last_n_months_average_monthly_net, highest_sales_week
)
from watsonx_client import polish_text_with_fallback

app = FastAPI(title="Syntri WhatsApp Financial Bot")

# Enhanced query keywords for better detection
QUERY_KEYWORDS = [
    "how am i doing", "this week", "last week", "total sales", "total expenses", "net profit",
    "projected", "if i hire", "what if i hire", "what if", "highest sales", "month", "months", 
    "in august", "july", "august", "september", "october", "november", "december",
    "january", "february", "march", "april", "may", "june",
    "sales this", "expenses this", "profit this", "how much", "revenue", "income",
    "weekly report", "monthly report", "summary", "overview"
]

def is_query(text: str) -> bool:
    """
    Enhanced query detection with better heuristics.
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # Explicit query indicators
    query_indicators = [
        "?", "how", "what", "when", "where", "why", "which", "tell me", 
        "show me", "give me", "can you", "could you", "would you"
    ]
    
    # Check for explicit query indicators
    if any(indicator in text_lower for indicator in query_indicators):
        return True
    
    # Check for query keywords
    for keyword in QUERY_KEYWORDS:
        if keyword in text_lower:
            return True
    
    # Check for analytical patterns
    analytical_patterns = [
        "if i", "what if", "projected", "projection", "forecast", "predict",
        "analyze", "analysis", "compare", "comparison", "trend", "growth"
    ]
    
    if any(pattern in text_lower for pattern in analytical_patterns):
        return True
    
    # Check for time-based queries without amounts
    time_patterns = ["this week", "last week", "this month", "last month"]
    has_time_pattern = any(pattern in text_lower for pattern in time_patterns)
    has_amount = any(char.isdigit() for char in text_lower) or "₹" in text_lower
    
    if has_time_pattern and not has_amount:
        return True
    
    # If it contains "sales on" or "expenses on" without clear amounts, likely a query
    if ("sales on" in text_lower or "expenses on" in text_lower):
        if not has_amount:
            return True
    
    return False

def log_conversation(user_from: str, incoming_text: str, reply_text: str, meta: dict = None):
    """
    Log conversation with enhanced metadata.
    """
    try:
        conversations.insert_one({
            "from": user_from,
            "incoming": incoming_text,
            "reply": reply_text,
            "meta": meta or {},
            "ts": datetime.utcnow(),
            "success": True
        })
    except Exception as e:
        print(f"❌ Failed to log conversation: {e}")

def format_basic_insight(ins: dict) -> str:
    """
    Format weekly insights with better readability.
    """
    week_start = ins['week_start'].strftime("%b %d")
    week_end = ins['week_end'].strftime("%b %d")
    
    return (f"📊 Week {week_start} - {week_end}\n"
           f"💰 Sales: ₹{ins['total_sales']:,.2f}\n"
           f"💸 Expenses: ₹{ins['total_expenses']:,.2f}\n"
           f"📈 Net Profit: ₹{ins['net_profit']:,.2f}")

def safe_send_message(to_number: str, message: str, conversation_meta: dict = None):
    """
    Safely send message with error handling.
    """
    try:
        send_whatsapp(to_number, message)
        log_conversation(to_number, "system_response", message, conversation_meta)
    except Exception as e:
        print(f"❌ Failed to send message: {e}")
        # Try to send a simpler error message
        try:
            send_whatsapp(to_number, "⚠️ Technical error occurred. Please try again.")
        except:
            print("❌ Failed to send even the error message")

async def process_image_message(form_data: dict):
    """
    Process incoming image messages with enhanced error handling.
    """
    from_number = form_data.get("From")
    media_url = form_data.get("MediaUrl0")
    content_type = form_data.get("MediaContentType0")
    
    try:
        print(f"📷 Processing image from {from_number}")
        print(f"🔗 Media URL: {media_url}")
        print(f"📋 Content Type: {content_type}")
        
        # Download media
        image_bytes = download_media(media_url)
        
        # Validate image
        if not validate_image(image_bytes):
            raise ValueError("Invalid image format")
        
        # Extract text using OCR
        extracted_text = image_bytes_to_text(image_bytes)
        
        # Log media input
        media_inputs.insert_one({
            "from": from_number,
            "media_url": media_url,
            "content_type": content_type,
            "ocr_text": extracted_text,
            "received_at": datetime.utcnow(),
            "processing_status": "success"
        })
        
        # Parse the extracted text
        parsed_data = parse_text_message(extracted_text, source="photo")
        
        # Store the financial record
        financial_records.insert_one(parsed_data)
        
        # Send confirmation with extracted details
        amount_str = f"₹{parsed_data['amount']:,.2f}" if parsed_data['amount'] else "No amount detected"
        success_message = (f"✅ Image processed successfully!\n"
                         f"📝 Extracted: {extracted_text[:100]}...\n"
                         f"💰 Amount: {amount_str}\n"
                         f"🏷️ Type: {parsed_data['type'].title()}")
        
        safe_send_message(from_number, success_message, {
            "type": "ingest", 
            "source": "photo", 
            "extracted_text": extracted_text,
            "parsed_amount": parsed_data['amount']
        })
        
    except Exception as e:
        print(f"❌ Image processing error: {e}")
        print(f"🔍 Traceback: {traceback.format_exc()}")
        
        # Log the failed attempt
        try:
            media_inputs.insert_one({
                "from": from_number,
                "media_url": media_url,
                "content_type": content_type,
                "error": str(e),
                "received_at": datetime.utcnow(),
                "processing_status": "failed"
            })
        except:
            pass
        
        # Send user-friendly error message
        error_message = ("❌ Sorry, I couldn't process that image.\n"
                        "Please try:\n"
                        "• Taking a clearer photo\n"
                        "• Ensuring good lighting\n"
                        "• Or typing the details manually")
        
        safe_send_message(from_number, error_message, {
            "type": "error", 
            "error": str(e)
        })

async def process_text_query(from_number: str, text: str):
    """
    Process text queries with enhanced query handling.
    """
    text_lower = text.lower()
    
    try:
        # Weekly insights
        if "this week" in text_lower or "how am i doing" in text_lower:
            insights = compute_weekly_insights(db=db)
            raw_reply = format_basic_insight(insights)
            polished = polish_text_with_fallback(raw_reply)
            safe_send_message(from_number, polished, {
                "type": "query", "subtype": "weekly_insight"
            })
            return

        # Last week insights
        if "last week" in text_lower:
            from dateutil.relativedelta import relativedelta
            target = datetime.utcnow() - relativedelta(weeks=1)
            insights = compute_weekly_insights(db=db, target_date=target)
            raw_reply = format_basic_insight(insights)
            polished = polish_text_with_fallback(raw_reply)
            safe_send_message(from_number, polished, {
                "type": "query", "subtype": "last_week"
            })
            return

        # Monthly queries
        import re
        month_match = re.search(
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?', 
            text_lower
        )
        if month_match:
            month_name = month_match.group(1)
            year = int(month_match.group(2)) if month_match.group(2) else datetime.utcnow().year
            
            month_map = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }
            month = month_map[month_name]
            
            totals = compute_monthly_totals(db=db, year=year, month=month)
            raw_reply = (f"📅 {month_name.title()} {year} Summary:\n"
                        f"💰 Sales: ₹{totals['sales']:,.2f}\n"
                        f"💸 Expenses: ₹{totals['expenses']:,.2f}\n"
                        f"📈 Net Profit: ₹{totals['net']:,.2f}")
            
            polished = polish_text_with_fallback(raw_reply)
            safe_send_message(from_number, polished, {
                "type": "query", "subtype": "monthly", "year": year, "month": month
            })
            return

        # Hiring simulation
        if "hire" in text_lower and ("if" in text_lower or "what if" in text_lower):
            salary = extract_amount_from_query(text)
            simulation = simulate_hire(db=db, monthly_salary=salary, months=6)
            
            lines = [f"👥 Hiring Analysis (₹{salary:,.0f}/month):"]
            lines.append(f"📊 Current avg monthly net: ₹{simulation['base_monthly_net']:,.2f}")
            
            for i, proj in enumerate(simulation["projection"][:3]):  # Show first 3 months
                lines.append(f"Month {proj['month']}: ₹{proj['projected_net_after_salary']:,.2f}")
            
            raw_reply = "\n".join(lines)
            polished = polish_text_with_fallback(raw_reply)
            safe_send_message(from_number, polished, {
                "type": "query", "subtype": "hire", "salary": salary
            })
            return

        # Sales change simulation
        if "sales" in text_lower and ("drop" in text_lower or "increase" in text_lower or "%" in text):
            pct = 0.0
            pct_match = re.search(r'(-?\d+(?:\.\d+)?)\s*%?', text)
            if pct_match:
                try:
                    pct_val = float(pct_match.group(1))
                    pct = -abs(pct_val)/100.0 if "drop" in text_lower or "decrease" in text_lower else abs(pct_val)/100.0
                except:
                    pct = 0.0
            
            simulation = simulate_sales_change(db=db, pct_change=pct, months=6)
            change_desc = "increase" if pct > 0 else "decrease"
            raw_reply = (f"📈 Sales {change_desc} simulation ({pct*100:+.0f}%):\n"
                        f"📊 Base monthly net: ₹{simulation['base_monthly_net']:,.2f}\n"
                        f"📅 Month 1 projection: ₹{simulation['projection'][0]['projected_net']:,.2f}")
            
            polished = polish_text_with_fallback(raw_reply)
            safe_send_message(from_number, polished, {
                "type": "query", "subtype": "sales_change", "pct": pct
            })
            return

        # Highest sales week
        if "highest sales" in text_lower or "highest week" in text_lower or "best week" in text_lower:
            highest = highest_sales_week(db=db)
            if not highest:
                raw_reply = "📊 No sales data found in records."
            else:
                raw_reply = (f"🏆 Best performing week:\n"
                           f"📅 Year {highest['year']}, Week {highest['week']}\n"
                           f"💰 Sales: ₹{highest['sales']:,.2f}")
            
            polished = polish_text_with_fallback(raw_reply)
            safe_send_message(from_number, polished, {
                "type": "query", "subtype": "highest_sales"
            })
            return

        # General financial summary
        if any(word in text_lower for word in ["sales", "expenses", "net", "profit", "summary", "overview"]):
            avg_data = last_n_months_average_monthly_net(db=db, n=3)
            avg_net = avg_data.get("average_monthly_net", 0.0)
            
            now = datetime.utcnow()
            current_month = compute_monthly_totals(db=db, year=now.year, month=now.month)
            
            raw_reply = (f"📊 Financial Summary:\n"
                        f"📅 This month: ₹{current_month['sales']:,.2f} sales, "
                        f"₹{current_month['expenses']:,.2f} expenses, "
                        f"₹{current_month['net']:,.2f} net\n"
                        f"📈 3-month avg net: ₹{avg_net:,.2f}")
            
            polished = polish_text_with_fallback(raw_reply)
            safe_send_message(from_number, polished, {
                "type": "query", "subtype": "summary"
            })
            return

        # Fallback for unrecognized queries
        fallback_message = ("🤔 I didn't understand that query.\n\n"
                           "Try asking:\n"
                           "• 'How am I doing this week?'\n"
                           "• 'Total sales in August'\n"
                           "• 'What if I hire someone for ₹15000?'\n"
                           "• 'Highest sales week'\n"
                           "• Or send a bill/receipt image")
        
        polished = polish_text_with_fallback(fallback_message)
        safe_send_message(from_number, polished, {
            "type": "query", "subtype": "fallback"
        })

    except Exception as e:
        print(f"❌ Query processing error: {e}")
        print(f"🔍 Traceback: {traceback.format_exc()}")
        
        error_message = ("⚠️ Sorry, I encountered an error processing your query.\n"
                        "Please try again or rephrase your question.")
        safe_send_message(from_number, error_message, {
            "type": "error", "error": str(e)
        })

async def process_text_ingestion(from_number: str, text: str):
    """
    Process text for data ingestion.
    """
    try:
        parsed_data = parse_text_message(text, source="text")
        financial_records.insert_one(parsed_data)
        
        # Enhanced confirmation message
        amount_str = f"₹{parsed_data['amount']:,.2f}" if parsed_data['amount'] else "Amount not detected"
        confirmation = (f"✅ Record added!\n"
                       f"💰 {amount_str}\n"
                       f"🏷️ {parsed_data['type'].title()}: {parsed_data['category']}")
        
        safe_send_message(from_number, confirmation, {
            "type": "ingest", "source": "text"
        })
        
    except Exception as e:
        print(f"❌ Ingestion error: {e}")
        error_message = "❌ Sorry, I couldn't process that entry. Please check the format and try again."
        safe_send_message(from_number, error_message, {
            "type": "error", "error": str(e)
        })

async def process_incoming(form_data: dict):
    """
    Main processing function for incoming WhatsApp messages.
    """
    from_number = form_data.get("From", "unknown")
    body = form_data.get("Body", "").strip()
    num_media = int(form_data.get("NumMedia", "0"))
    
    print(f"📱 Processing message from {from_number}")
    
    # Handle media messages (images)
    if num_media > 0:
        await process_image_message(form_data)
        return
    
    # Handle empty messages
    if not body:
        safe_send_message(from_number, 
                         "👋 Hi! Send me your financial data or ask about your business performance.\n\n"
                         "You can:\n"
                         "• Send photos of bills/receipts\n"
                         "• Type financial transactions\n"
                         "• Ask 'How am I doing this week?'")
        return
    
    # Determine if it's a query or data ingestion
    if is_query(body):
        await process_text_query(from_number, body)
    else:
        await process_text_ingestion(from_number, body)

@app.post("/webhook/twilio")
async def twilio_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Enhanced webhook endpoint with better error handling.
    """
    try:
        form = await request.form()
        data = dict(form)
        print(f"📩 Incoming Twilio webhook: {data}")
        
        # Add background task for processing
        background_tasks.add_task(process_incoming, data)
        
        return Response(content="OK", status_code=200)
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        print(f"🔍 Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "message": "Syntri WhatsApp Financial Bot API",
        "version": "2.0.0",
        "endpoints": {
            "webhook": "/webhook/twilio",
            "health": "/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)