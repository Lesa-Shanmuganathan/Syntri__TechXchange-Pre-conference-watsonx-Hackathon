import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Tuple, Dict, Any
from prophet import Prophet
from sklearn.linear_model import LinearRegression
import logging
from app.database import get_sync_database
from app.models.schemas import Forecast

logger = logging.getLogger(__name__)

class ForecastingService:
    def __init__(self):
        self.db = get_sync_database()
    
    async def get_daily_balance_series(self, start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """Get daily balance series from financial records"""
        if start_date is None:
            start_date = date.today() - timedelta(days=60)
        if end_date is None:
            end_date = date.today()
        
        # Get financial records
        records = list(self.db.financial_records.find({
            "date": {"$gte": start_date, "$lte": end_date}
        }))
        
        if not records:
            logger.warning("No financial records found")
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        
        # Calculate daily flows
        daily_flows = df.groupby(['date', 'type'])['amount'].sum().unstack(fill_value=0)
        if 'inflow' not in daily_flows.columns:
            daily_flows['inflow'] = 0
        if 'outflow' not in daily_flows.columns:
            daily_flows['outflow'] = 0
        
        daily_flows['net_flow'] = daily_flows['inflow'] - daily_flows['outflow']
        
        # Create complete date range
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        daily_series = pd.DataFrame(index=date_range)
        daily_series = daily_series.join(daily_flows, how='left').fillna(0)
        
        # Calculate cumulative balance (assuming starting balance of ₹20,000)
        starting_balance = 20000
        daily_series['balance'] = starting_balance + daily_series['net_flow'].cumsum()
        
        return daily_series.reset_index().rename(columns={'index': 'ds', 'balance': 'y'})
    
    async def forecast_balance(self, days_ahead: int = 7) -> List[Forecast]:
        """Generate balance forecast using Prophet or fallback methods"""
        df = await self.get_daily_balance_series()
        
        if df.empty or len(df) < 7:
            logger.warning("Insufficient data for forecasting")
            return []
        
        try:
            if len(df) >= 21:  # Use Prophet for sufficient data
                forecasts = await self._prophet_forecast(df, days_ahead)
            else:  # Use simple method for sparse data
                forecasts = await self._simple_forecast(df, days_ahead)
            
            return forecasts
        except Exception as e:
            logger.error(f"Forecasting failed: {e}")
            return []
    
    async def _prophet_forecast(self, df: pd.DataFrame, days_ahead: int) -> List[Forecast]:
        """Prophet-based forecasting"""
        model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,
            interval_width=0.8
        )
        
        model.fit(df[['ds', 'y']])
        
        future = model.make_future_dataframe(periods=days_ahead)
        forecast = model.predict(future)
        
        # Extract future forecasts
        future_forecast = forecast.tail(days_ahead)
        
        forecasts = []
        for _, row in future_forecast.iterrows():
            forecasts.append(Forecast(
                date=row['ds'].date(),
                predicted_balance=float(row['yhat']),
                lower_bound=float(row['yhat_lower']),
                upper_bound=float(row['yhat_upper']),
                confidence=0.8
            ))
        
        return forecasts
    
    async def _simple_forecast(self, df: pd.DataFrame, days_ahead: int) -> List[Forecast]:
        """Simple linear regression fallback"""
        df['day_num'] = range(len(df))
        
        X = df[['day_num']].values
        y = df['y'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        forecasts = []
        last_day = len(df)
        last_date = df['ds'].iloc[-1].date()
        
        for i in range(1, days_ahead + 1):
            future_day = last_day + i
            pred = model.predict([[future_day]])[0]
            
            # Simple confidence interval (±10% of prediction)
            margin = abs(pred) * 0.1
            
            forecasts.append(Forecast(
                date=last_date + timedelta(days=i),
                predicted_balance=float(pred),
                lower_bound=float(pred - margin),
                upper_bound=float(pred + margin),
                confidence=0.6
            ))
        
        return forecasts
    
    async def detect_breach(self, forecasts: List[Forecast], threshold: float) -> Tuple[bool, Dict[str, Any]]:
        """Detect if balance will breach threshold"""
        for i, forecast in enumerate(forecasts):
            if forecast.lower_bound < threshold:
                return True, {
                    'days_to_breach': i + 1,
                    'breach_date': forecast.date,
                    'projected_balance': forecast.predicted_balance,
                    'severity': 'critical' if forecast.lower_bound < threshold * 0.5 else 'warning'
                }
        
        return False, {}
    
    async def simulate_action(self, action: Dict[str, Any], forecasts: List[Forecast]) -> List[Forecast]:
        """Simulate the effect of an action on forecasts"""
        simulated_forecasts = forecasts.copy()
        
        if action['type'] == 'delay_payment':
            # Delay outflow by specified days
            delay_days = action.get('delay_days', 2)
            amount = action.get('amount', 0)
            
            # Find the breach date and add cash back
            for i, forecast in enumerate(simulated_forecasts):
                if i < delay_days:
                    forecast.predicted_balance += amount
                    forecast.lower_bound += amount
                    forecast.upper_bound += amount
        
        elif action['type'] == 'early_collection':
            # Pull receivable forward
            amount = action.get('amount', 0)
            
            # Add cash immediately
            for forecast in simulated_forecasts:
                forecast.predicted_balance += amount
                forecast.lower_bound += amount
                forecast.upper_bound += amount
        
        elif action['type'] == 'pause_subscription':
            # Stop recurring outflow
            amount = action.get('amount', 0)
            
            for forecast in simulated_forecasts:
                forecast.predicted_balance += amount
                forecast.lower_bound += amount
                forecast.upper_bound += amount
        
        return simulated_forecasts