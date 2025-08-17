# parser.py
import re
from dateutil import parser as dtparser
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

# Enhanced amount detection patterns
AMOUNT_PATTERNS = [
    r'₹\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # ₹1,000.00
    r'INR\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # INR 1000
    r'Rs\.?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Rs. 1000
    r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*₹',  # 1000₹
    r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*rupees?',  # 1000 rupees
    r'(?:amount|total|sum|paid|received|cost|price)[\s:]+₹?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # amount: 1000
    r'(\d+(?:,\d{3})*(?:\.\d{2})?)',  # Simple number pattern (last resort)
]

# Enhanced category keywords with more specific patterns
CATEGORY_KEYWORDS = {
    "supplier_payment": [
        "supplier", "vendor", "paid to supplier", "payment to vendor", 
        "wholesale purchase", "stock purchase", "raw material", "inventory"
    ],
    "salary": [
        "salary", "salaries", "wages", "staff payment", "employee", 
        "payroll", "worker payment", "labor cost"
    ],
    "diesel": [
        "diesel", "fuel", "petrol", "gas", "vehicle fuel", "transportation fuel"
    ],
    "grocery": [
        "grocery", "kirana", "vegetables", "food items", "provisions", 
        "household items", "daily needs"
    ],
    "electronics": [
        "electronics", "mobile", "tv", "television", "appliance", 
        "computer", "laptop", "phone", "gadget"
    ],
    "sale": [
        "sale", "sold", "income", "received", "revenue", "earnings", 
        "customer payment", "order completed", "delivery payment"
    ],
    "rent": [
        "rent", "rental", "lease", "shop rent", "office rent", "space rent"
    ],
    "utilities": [
        "electricity", "water", "gas bill", "internet", "phone bill", 
        "utility", "electric bill", "power bill"
    ],
    "maintenance": [
        "repair", "maintenance", "service", "fixing", "renovation", "upkeep"
    ],
    "transportation": [
        "transport", "delivery", "shipping", "courier", "logistics", "vehicle"
    ],
    "marketing": [
        "advertisement", "marketing", "promotion", "advertising", "publicity"
    ],
    "office_supplies": [
        "stationery", "office supplies", "paper", "printing", "ink"
    ],
    "insurance": [
        "insurance", "policy", "premium", "coverage"
    ],
    "tax": [
        "tax", "gst", "income tax", "sales tax", "vat"
    ],
    "misc": ["misc", "other", "miscellaneous", "unknown", "general"]
}

# Transaction type indicators
TYPE_INDICATORS = {
    "expense": [
        "paid", "spent", "purchase", "bought", "paid to", "expense", "cost",
        "bill", "payment", "outgoing", "debit", "withdrawal", "given"
    ],
    "sale": [
        "received", "got", "sold", "sale", "income", "revenue", "earnings",
        "payment received", "customer paid", "incoming", "credit", "deposit"
    ]
}

# Date patterns for better extraction
DATE_PATTERNS = [
    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # DD/MM/YYYY or DD-MM-YYYY
    r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{2,4})',  # DD Month YYYY
    r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{2,4})',  # Month DD, YYYY
    r'(today|yesterday)',  # Relative dates
    r'(\d{1,2}\s+(?:days?|weeks?)\s+ago)',  # X days ago
]

def extract_amount(text: str) -> Optional[float]:
    """
    Enhanced amount extraction with multiple pattern matching.
    """
    if not text:
        return None
    
    # Clean up the text
    text = text.replace("\u202f", " ").replace("₹", "₹").strip()
    
    # Try each pattern in order of specificity
    for pattern in AMOUNT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            for match in matches:
                try:
                    # Clean the matched amount
                    amount_str = str(match).replace(",", "").strip()
                    amount = float(amount_str)
                    
                    # Validate the amount (reasonable business range)
                    if 0 < amount <= 10000000:  # Up to 1 crore
                        return amount
                        
                except (ValueError, TypeError):
                    continue
    
    # Try to extract from words (e.g., "five thousand")
    word_amount = extract_amount_from_words(text)
    if word_amount:
        return word_amount
    
    return None

def extract_amount_from_words(text: str) -> Optional[float]:
    """
    Extract amounts written in words (e.g., "five thousand").
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Number words mapping
    word_to_num = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
        'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
        'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
        'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000,
        'lakh': 100000, 'crore': 10000000
    }
    
    # Simple patterns for common amounts
    patterns = [
        (r'(\w+)\s+thousand', lambda m: word_to_num.get(m.group(1), 0) * 1000),
        (r'(\w+)\s+hundred', lambda m: word_to_num.get(m.group(1), 0) * 100),
        (r'(\w+)\s+lakh', lambda m: word_to_num.get(m.group(1), 0) * 100000),
    ]
    
    for pattern, converter in patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                return converter(match)
            except:
                continue
    
    return None

def extract_date(text: str) -> Optional[datetime]:
    """
    Enhanced date extraction with multiple strategies.
    """
    if not text:
        return None
    
    # Handle relative dates first
    text_lower = text.lower()
    now = datetime.now()
    
    if 'today' in text_lower:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif 'yesterday' in text_lower:
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Handle "X days ago" patterns
    days_ago_match = re.search(r'(\d+)\s+days?\s+ago', text_lower)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Try specific date patterns
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                parsed_date = dtparser.parse(match, fuzzy=True, dayfirst=True)
                
                # Validate date (not too far in future or past)
                if (now - timedelta(days=365*2)) <= parsed_date <= (now + timedelta(days=30)):
                    return parsed_date
                    
            except (ValueError, TypeError):
                continue
    
    # Fallback to fuzzy parsing on the entire text
    try:
        parsed_date = dtparser.parse(text, fuzzy=True, dayfirst=True)
        
        # Validate date
        if (now - timedelta(days=365*2)) <= parsed_date <= (now + timedelta(days=30)):
            return parsed_date
            
    except (ValueError, TypeError):
        pass
    
    return None

def detect_category(text: str) -> str:
    """
    Enhanced category detection with weighted scoring.
    """
    if not text:
        return "uncategorized"
    
    text_lower = text.lower()
    category_scores = {}
    
    # Score each category based on keyword matches
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in text_lower:
                # Give higher scores to more specific keywords
                score += len(keyword.split())
        
        if score > 0:
            category_scores[category] = score
    
    # Return the category with the highest score
    if category_scores:
        return max(category_scores, key=category_scores.get)
    
    return "uncategorized"

def detect_type(text: str) -> str:
    """
    Enhanced transaction type detection.
    """
    if not text:
        return "unknown"
    
    text_lower = text.lower()
    
    # Score each type based on indicators
    expense_score = sum(1 for indicator in TYPE_INDICATORS["expense"] if indicator in text_lower)
    sale_score = sum(1 for indicator in TYPE_INDICATORS["sale"] if indicator in text_lower)
    
    # Check category for additional hints
    category = detect_category(text)
    if category == "sale":
        sale_score += 2
    elif category in ["supplier_payment", "salary", "diesel", "grocery", "utilities", "rent"]:
        expense_score += 2
    
    # Return the type with higher score
    if expense_score > sale_score:
        return "expense"
    elif sale_score > expense_score:
        return "sale"
    
    return "unknown"

def parse_text_message(text: str, source: str = "text") -> Dict:
    """
    Enhanced text parsing with comprehensive data extraction.
    """
    if not text:
        text = ""
    
    # Extract components
    amount = extract_amount(text)
    date = extract_date(text) or datetime.utcnow()
    category = detect_category(text)
    transaction_type = detect_type(text)
    
    # Additional metadata
    confidence_score = calculate_confidence_score(text, amount, category, transaction_type)
    
    parsed_data = {
        "date": date,
        "type": transaction_type,
        "category": category,
        "amount": amount,
        "raw_text": text.strip(),
        "source": source,
        "ingested_at": datetime.utcnow(),
        "confidence_score": confidence_score,
        "parser_version": "2.0"
    }
    
    return parsed_data

def calculate_confidence_score(text: str, amount: float, category: str, transaction_type: str) -> float:
    """
    Calculate confidence score for the parsed data.
    """
    score = 0.0
    
    # Amount confidence
    if amount and amount > 0:
        score += 0.4
    
    # Category confidence
    if category != "uncategorized":
        score += 0.3
    
    # Type confidence
    if transaction_type != "unknown":
        score += 0.3
    
    # Text quality (length and structure)
    if text and len(text.split()) >= 3:
        score += 0.1
    
    # Cap at 1.0
    return min(score, 1.0)

def extract_amount_from_query(text: str) -> float:
    """
    Enhanced amount extraction for query contexts (e.g., "what if I hire 15k").
    """
    amount = extract_amount(text)
    if amount is not None:
        return amount
    
    # Look for patterns like "15k", "20K", "1.5L"
    k_pattern = re.search(r'(\d+(?:\.\d+)?)\s*[kK]', text)
    if k_pattern:
        return float(k_pattern.group(1)) * 1000.0
    
    # Look for lakh patterns
    l_pattern = re.search(r'(\d+(?:\.\d+)?)\s*[lL]', text)
    if l_pattern:
        return float(l_pattern.group(1)) * 100000.0
    
    # Look for crore patterns
    c_pattern = re.search(r'(\d+(?:\.\d+)?)\s*[cC]', text)
    if c_pattern:
        return float(c_pattern.group(1)) * 10000000.0
    
    return 0.0

def validate_parsed_data(parsed_data: Dict) -> List[str]:
    """
    Validate parsed data and return list of warnings/issues.
    """
    warnings = []
    
    if not parsed_data.get("amount") or parsed_data["amount"] <= 0:
        warnings.append("No valid amount detected")
    
    if parsed_data.get("type") == "unknown":
        warnings.append("Transaction type could not be determined")
    
    if parsed_data.get("category") == "uncategorized":
        warnings.append("Transaction category could not be determined")
    
    if parsed_data.get("confidence_score", 0) < 0.5:
        warnings.append("Low confidence in parsed data")
    
    return warnings