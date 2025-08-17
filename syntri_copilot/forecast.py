# forecast.py
from datetime import datetime, timedelta
from pymongo import DESCENDING
import pandas as pd
from dateutil.relativedelta import relativedelta

def to_range_for_week(target_date: datetime):
    # week Monday..Sunday
    start = (target_date - timedelta(days=target_date.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start, end

def compute_weekly_insights(db, target_date: datetime = None):
    if target_date is None:
        target_date = datetime.utcnow()
    start, end = to_range_for_week(target_date)
    pipeline = [
        {"$match": {"date": {"$gte": start, "$lte": end}}},
        {"$group": {"_id": "$type", "total": {"$sum": {"$ifNull": ["$amount", 0]}}}} 
    ]
    res = list(db.financial_records.aggregate(pipeline))
    totals = {r["_id"]: r["total"] for r in res}
    total_sales = totals.get("sale", 0)
    total_expenses = totals.get("expense", 0)
    net = total_sales - total_expenses
    return {"week_start": start, "week_end": end, "total_sales": total_sales, "total_expenses": total_expenses, "net_profit": net}

def compute_monthly_totals(db, year:int, month:int):
    start = datetime(year, month, 1)
    end = (start + relativedelta(months=1)) - timedelta(seconds=1)
    pipeline = [
        {"$match": {"date": {"$gte": start, "$lte": end}}},
        {"$group": {"_id": "$type", "total": {"$sum": {"$ifNull": ["$amount", 0]}}}}
    ]
    res = list(db.financial_records.aggregate(pipeline))
    totals = {r["_id"]: r["total"] for r in res}
    return {"year": year, "month": month, "sales": totals.get("sale", 0), "expenses": totals.get("expense", 0), "net": totals.get("sale",0) - totals.get("expense",0)}

def last_n_months_average_monthly_net(db, n=3):
    now = datetime.utcnow()
    start = now - relativedelta(months=n)
    pipeline = [
        {"$match": {"date": {"$gte": start, "$lte": now}}},
        {"$group": {"_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}, "type": "$type"}, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]
    res = list(db.financial_records.aggregate(pipeline))
    # Build month-wise nets
    df_rows = {}
    for r in res:
        key = (r["_id"]["year"], r["_id"]["month"])
        df_rows.setdefault(key, {"sale":0,"expense":0})
        if r["_id"]["type"] == "sale":
            df_rows[key]["sale"] = r["total"]
        else:
            df_rows[key]["expense"] = r["total"]
    nets = []
    for k,v in df_rows.items():
        nets.append(v.get("sale",0)-v.get("expense",0))
    if not nets:
        return {"average_monthly_net": 0.0}
    avg = sum(nets)/len(nets)
    return {"average_monthly_net": avg}

def simulate_hire(db, monthly_salary: float, months=6):
    # base monthly net = average monthly net for last 3 months
    base = last_n_months_average_monthly_net(db, n=3).get("average_monthly_net", 0.0)
    running = base
    projection = []
    for m in range(1, months+1):
        running_after = running - monthly_salary
        projection.append({"month": m, "projected_net_after_salary": running_after})
        running = running_after
    return {"base_monthly_net": base, "monthly_salary": monthly_salary, "projection": projection}

def simulate_sales_change(db, pct_change: float, months=6):
    # pct_change is decimal: 0.1 -> +10% sales, -0.2 -> -20% sales
    # base monthly net:
    base = last_n_months_average_monthly_net(db, n=3).get("average_monthly_net", 0.0)
    # naive: base scales with sales change
    projection = []
    running_base = base
    for m in range(1, months+1):
        running_after = running_base * (1 + pct_change)
        projection.append({"month": m, "projected_net": running_after})
        running_base = running_after
    return {"base_monthly_net": base, "pct_change": pct_change, "projection": projection}

def highest_sales_week(db):
    # aggregate weekly (ISO week-year) sales totals and pick max
    pipeline = [
        {"$match": {"type": "sale"}},
        {"$project": {"year": {"$year": "$date"}, "week": {"$isoWeek": "$date"}, "amount": {"$ifNull": ["$amount", 0]}}},
        {"$group": {"_id": {"year": "$year", "week": "$week"}, "total": {"$sum": "$amount"}}},
        {"$sort": {"total": -1}},
        {"$limit": 1}
    ]
    res = list(db.financial_records.aggregate(pipeline))
    if not res:
        return None
    r = res[0]
    return {"year": r["_id"]["year"], "week": r["_id"]["week"], "sales": r["total"]}
