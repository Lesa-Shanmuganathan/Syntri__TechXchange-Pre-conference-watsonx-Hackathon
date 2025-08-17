# main_module.py
import os
import io
import base64
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
from twilio.rest import Client as TwilioClient

from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

# --- Load environment variables ---
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "syntri")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "financial_records")

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Kolkata"))

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")
TWILIO_TO = os.getenv("TWILIO_TO")

IBM_WATSONX_API_KEY = os.getenv("IBM_WATSONX_API_KEY")
IBM_WATSONX_URL = os.getenv("IBM_WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
IBM_WATSONX_PROJECT_ID = os.getenv("IBM_WATSONX_PROJECT_ID")
# Updated to use newer model instead of deprecated one
WATSONX_MODEL_ID = os.getenv("WATSONX_MODEL_ID", "ibm/granite-3-3-8b-instruct")

# Optional: Add ImgBB API key for more reliable image hosting
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")  # Get free API key from imgbb.com


def rupees(n: float) -> str:
    """Format number as Indian Rupees with proper sign and formatting."""
    return f"{'-' if n < 0 else ''}₹{abs(n):,.0f}"


def fetch_last_7_days_df() -> pd.DataFrame:
    """Fetch cash balance data for last 7 days from MongoDB."""
    try:
        client = MongoClient(MONGO_URI, tz_aware=True)
        col = client[MONGO_DB][MONGO_COLLECTION]

        today = datetime.now(TZ).date()
        start = today - timedelta(days=6)

        # Updated query to match your data structure
        q = {
            "type": "cash_balance",
            "business_id": BUSINESS_ID,
            "date": {"$gte": start.isoformat(), "$lte": today.isoformat()}
        }

        rows = list(col.find(q).sort("date", 1))
        if not rows:
            print(f"[DEBUG] No records found for query: {q}")
            raise RuntimeError("No cash_balance records found for last 7 days.")

        df = pd.DataFrame(rows)
        
        # Handle both 'cash_balance' and 'amount' field names
        balance_field = 'cash_balance' if 'cash_balance' in df.columns else 'amount'
        
        # Convert date field properly
        if 'date' in df.columns:
            # Handle both string dates and datetime objects
            if df['date'].dtype == 'object':
                try:
                    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
                except:
                    df["date"] = pd.to_datetime(df["date"])
            else:
                df["date"] = pd.to_datetime(df["date"])
        
        # Ensure we have the right columns
        result_df = df[["date", balance_field]].copy()
        result_df = result_df.rename(columns={balance_field: 'cash_balance'})
        
        client.close()
        return result_df.sort_values("date")
        
    except Exception as e:
        print(f"[ERROR] Database fetch failed: {e}")
        raise


def compute_kpis(df: pd.DataFrame) -> Dict:
    """Compute key performance indicators from the cash balance data."""
    bal = df["cash_balance"].astype(float)
    dates = df["date"].dt.date.tolist()
    
    return {
        "start": dates[0],
        "end": dates[-1],
        "highest": float(bal.max()),
        "highest_date": df.loc[bal.idxmax(), "date"].date(),
        "lowest": float(bal.min()),
        "lowest_date": df.loc[bal.idxmin(), "date"].date(),
        "net_change": float(bal.iloc[-1] - bal.iloc[0]),
        "pct_change": (float(bal.iloc[-1] - bal.iloc[0]) / bal.iloc[0] * 100 if bal.iloc[0] != 0 else 0.0),
        "trend": "Upward" if bal.iloc[-1] >= bal.iloc[0] else "Downward",
        "start_balance": float(bal.iloc[0]),
        "end_balance": float(bal.iloc[-1])
    }


def make_chart(df: pd.DataFrame) -> bytes:
    """Create a professional cash balance chart."""
    plt.rcParams.update({
        "figure.figsize": (12, 6),
        "axes.grid": True,
        "grid.alpha": 0.3,
        "font.size": 10
    })

    fig, ax = plt.subplots()
    
    # Create the line plot with better styling
    line = ax.plot(df["date"], df["cash_balance"].astype(float), 
                  marker="o", linewidth=3, markersize=8, 
                  color='#2E86C1', markerfacecolor='#3498DB')[0]
    
    # Add fill under the line
    ax.fill_between(df["date"], df["cash_balance"].astype(float), 
                   alpha=0.2, color='#2E86C1')
    
    # Styling
    ax.set_title("Cash Balance Trend - Last 7 Days", fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Balance (₹)", fontsize=12)
    
    # Format y-axis to show values in lakhs/thousands
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"₹{x/1000:.0f}K" if x >= 1000 else f"₹{x:.0f}"))
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    fig.autofmt_xdate()
    
    # Add grid styling
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_facecolor('#FAFAFA')
    
    # Tight layout
    plt.tight_layout()
    
    # Save to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def polish_with_watsonx(raw: str) -> str:
    """Polish the raw summary using IBM Watson AI."""
    try:
        creds = Credentials(api_key=IBM_WATSONX_API_KEY, url=IBM_WATSONX_URL)
        params = {
            GenParams.MAX_NEW_TOKENS: 250,
            GenParams.TEMPERATURE: 0.3,
            GenParams.DECODING_METHOD: "greedy"
        }
        model = ModelInference(
            model_id=WATSONX_MODEL_ID,
            credentials=creds,
            params=params,
            project_id=IBM_WATSONX_PROJECT_ID
        )
        prompt = (
            "Rewrite the following 7-day cash flow update for a WhatsApp business message.\n"
            "Requirements:\n"
            "- Professional but conversational tone\n"
            "- Include a clear headline\n"
            "- Summarize key insights in bullet points\n"
            "- Use Indian Rupee formatting\n"
            "- Keep it concise for mobile reading\n"
            "- No emojis needed\n\n"
            f"Raw data:\n{raw}\n\n"
            "Polished message:"
        )
        res = model.generate_text(prompt=prompt)
        if isinstance(res, str):
            return res.strip()
        return res.get("results", [{}])[0].get("generated_text", raw).strip()
    except Exception as e:
        print(f"[WARN] Watson AI polishing failed: {e}")
        return raw  # Return raw text if AI fails


def upload_to_imgbb(png_bytes: bytes) -> Optional[str]:
    """Upload image to ImgBB (requires free API key)."""
    if not IMGBB_API_KEY:
        return None
        
    try:
        # Convert to base64
        img_b64 = base64.b64encode(png_bytes).decode('utf-8')
        
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": IMGBB_API_KEY,
                "image": img_b64,
                "name": f"cashflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            },
            timeout=15
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and data.get("data", {}).get("url"):
                return data["data"]["url"]
    except Exception as e:
        print(f"[WARN] ImgBB upload failed: {e}")
    
    return None


def upload_chart_png(png_bytes: bytes) -> str:
    """
    Upload chart PNG to image hosting services with multiple fallbacks.
    Returns direct link or raises RuntimeError if all fail.
    """
    # Try ImgBB first (most reliable if API key is available)
    if IMGBB_API_KEY:
        print("[INFO] Trying ImgBB upload...")
        url = upload_to_imgbb(png_bytes)
        if url:
            print(f"[SUCCESS] Uploaded to ImgBB: {url}")
            return url
    
    # Try catbox.moe (no API key required, reliable)
    try:
        print("[INFO] Trying catbox.moe upload...")
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": ("cashflow.png", png_bytes, "image/png")},
            timeout=15
        )
        if resp.status_code == 200 and resp.text.startswith("https://"):
            url = resp.text.strip()
            print(f"[SUCCESS] Uploaded to catbox.moe: {url}")
            return url
    except Exception as e:
        print(f"[WARN] catbox.moe upload failed: {e}")

    # Try file.io
    try:
        print("[INFO] Trying file.io upload...")
        resp = requests.post(
            "https://file.io",
            files={"file": ("cashflow.png", png_bytes, "image/png")},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and data.get("link"):
                url = data["link"]
                print(f"[SUCCESS] Uploaded to file.io: {url}")
                return url
    except Exception as e:
        print(f"[WARN] file.io upload failed: {e}")

    # Try 0x0.st as last resort
    try:
        print("[INFO] Trying 0x0.st upload...")
        resp = requests.post(
            "https://0x0.st",
            files={"file": ("cashflow.png", png_bytes, "image/png")},
            timeout=15
        )
        if resp.status_code == 200 and resp.text.strip().startswith("https://"):
            url = resp.text.strip()
            print(f"[SUCCESS] Uploaded to 0x0.st: {url}")
            return url
    except Exception as e:
        print(f"[WARN] 0x0.st upload failed: {e}")

    raise RuntimeError("Chart upload failed on all hosting services. Please check your internet connection.")


def send_whatsapp(body: str, media_url: str) -> str:
    """Send WhatsApp message via Twilio."""
    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=TWILIO_FROM,
            to=TWILIO_TO,
            body=body,
            media_url=[media_url] if media_url else None
        )
        return msg.sid
    except Exception as e:
        print(f"[ERROR] WhatsApp send failed: {e}")
        raise


if __name__ == "__main__":
    try:
        print("🚀 Starting Cash Flow Analytics...")
        
        # Fetch data
        print("📊 Fetching data from MongoDB...")
        df = fetch_last_7_days_df()
        print(f"✅ Found {len(df)} records")
        
        # Compute KPIs
        print("🧮 Computing KPIs...")
        kpis = compute_kpis(df)
        
        # Create day-by-day summary
        table_lines = [
            f"{d.strftime('%d %b')} → {rupees(v)}"
            for d, v in zip(df["date"], df["cash_balance"])
        ]
        table_text = "\n".join(table_lines)

        # Create raw summary
        raw_summary = (
            f"CASH FLOW SUMMARY\n"
            f"Period: {kpis['start'].strftime('%d %b')} to {kpis['end'].strftime('%d %b')}\n\n"
            f"Opening Balance: {rupees(kpis['start_balance'])}\n"
            f"Closing Balance: {rupees(kpis['end_balance'])}\n"
            f"Net Change: {'+' if kpis['net_change']>=0 else ''}{rupees(kpis['net_change'])} ({kpis['pct_change']:+.1f}%)\n"
            f"Trend: {kpis['trend']}\n\n"
            f"Peak: {rupees(kpis['highest'])} on {kpis['highest_date'].strftime('%d %b')}\n"
            f"Low: {rupees(kpis['lowest'])} on {kpis['lowest_date'].strftime('%d %b')}\n\n"
            f"Daily Breakdown:\n{table_text}"
        )

        # Polish with AI
        print("🤖 Polishing message with Watson AI...")
        polished = polish_with_watsonx(raw_summary)
        
        # Create chart
        print("📈 Generating chart...")
        chart_bytes = make_chart(df)
        
        # Upload chart
        print("☁️ Uploading chart...")
        chart_url = upload_chart_png(chart_bytes)
        
        # Send WhatsApp
        print("📱 Sending WhatsApp message...")
        sid = send_whatsapp(polished, chart_url)
        
        print(f"✅ SUCCESS! WhatsApp message sent.")
        print(f"📋 Message SID: {sid}")
        print(f"🖼️ Chart URL: {chart_url}")
        print(f"\n📄 Message Preview:\n{polished}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

        exit(1)
