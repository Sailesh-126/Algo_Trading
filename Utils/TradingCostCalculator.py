"""
Trading Cost Calculator
- Calculates daily average bid-ask spreads for each hour
- Stores hourly trading costs
- Provides interface to retrieve costs for backtesting and live trading
"""

import importlib
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path


class TradingCostCalculator:
    """Calculate and manage trading costs based on bid-ask spreads."""
    
    def __init__(self, symbol, days=30, interval='1h'):
        """
        Initialize TradingCostCalculator.
        
        Parameters
        ----------
        symbol : str
            Ticker symbol (e.g., 'EURUSD=X')
        days : int
            Number of days of historical data to analyze
        interval : str
            Data interval for bid-ask calculation (default '1h')
        """
        self.symbol = symbol
        self.days = days
        self.interval = interval
        self.hourly_costs = {}  # Dictionary to store hourly costs
        self.daily_costs = {}   # Dictionary to store daily average costs
        self._calculate_costs()
    
    def _calculate_costs(self):
        """Calculate bid-ask spreads from historical data."""
        if self._calculate_costs_ib():
            return

        try:
            self._calculate_costs_yahoo()
        except Exception as e:
            print(f"Error calculating trading costs with yfinance: {e}")
            self._set_default_costs()

    def _calculate_costs_ib(self):
        """Attempt to calculate bid-ask spread costs using ib_async historical data."""
        try:
            ib_async = importlib.import_module('ib_async')
            IB = getattr(ib_async, 'IB', None)
            if IB is None:
                raise ImportError('ib_async.IB not available')

            contract = self._build_ib_contract(ib_async)
            if contract is None:
                raise ValueError(f'Unable to build IB contract for symbol {self.symbol}')

            ib = IB()
            ib.connect()
            ib.qualifyContracts(contract)

            bid_bars = ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=f'{self.days} D',
                barSizeSetting=self._normalize_ib_interval(self.interval),
                whatToShow='BID',
                useRTH=True,
                formatDate=2,
                keepUpToDate=False
            )
            ask_bars = ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=f'{self.days} D',
                barSizeSetting=self._normalize_ib_interval(self.interval),
                whatToShow='ASK',
                useRTH=True,
                formatDate=2,
                keepUpToDate=False
            )

            ib.disconnect()

            if not bid_bars or not ask_bars:
                return False

            bid_df = pd.DataFrame([vars(bar) for bar in bid_bars])
            ask_df = pd.DataFrame([vars(bar) for bar in ask_bars])

            if bid_df.empty or ask_df.empty:
                return False

            if 'date' not in bid_df.columns or 'date' not in ask_df.columns:
                return False

            bid_df['datetime'] = pd.to_datetime(bid_df['date'])
            ask_df['datetime'] = pd.to_datetime(ask_df['date'])
            bid_df.set_index('datetime', inplace=True)
            ask_df.set_index('datetime', inplace=True)

            merged = bid_df[['close']].rename(columns={'close': 'bid_close'}).join(
                ask_df[['close']].rename(columns={'close': 'ask_close'}), how='inner'
            )

            if merged.empty:
                return False

            mid_price = (merged['ask_close'] + merged['bid_close']) / 2.0
            merged['spread'] = (merged['ask_close'] - merged['bid_close']) / mid_price
            merged['hour'] = merged.index.hour
            merged['date'] = merged.index.date

            hourly_avg = merged.groupby('hour')['spread'].mean()
            self.hourly_costs = hourly_avg.to_dict()
            daily_avg = merged.groupby('date')['spread'].mean()
            self.daily_costs = daily_avg.to_dict()

            return True
        except Exception as e:
            print(f'IB spread calculation failed: {e}')
            try:
                ib.disconnect()
            except Exception:
                pass
            return False

    def _build_ib_contract(self, ib_async):
        symbol = self.symbol
        if symbol.endswith('=X') and hasattr(ib_async, 'Forex'):
            return ib_async.Forex(symbol.replace('=X', ''))

        if '/' in symbol and hasattr(ib_async, 'Forex'):
            return ib_async.Forex(symbol.replace('/', ''))

        if hasattr(ib_async, 'Stock'):
            return ib_async.Stock(symbol)

        if hasattr(ib_async, 'Forex'):
            return ib_async.Forex(symbol)

        return None

    def _normalize_ib_interval(self, interval):
        mapping = {
            '1m': '1 min',
            '1min': '1 min',
            '5m': '5 mins',
            '15m': '15 mins',
            '30m': '30 mins',
            '1h': '1 hour',
            '2h': '2 hours',
            '4h': '4 hours',
            '1d': '1 day',
        }
        if interval in mapping:
            return mapping[interval]
        normalized = interval.lower().replace(' ', '')
        if normalized.endswith('h'):
            value = normalized[:-1]
            return f'{value} hour' + ('s' if value != '1' else '')
        if normalized.endswith('m'):
            value = normalized[:-1]
            return f'{value} min' + ('s' if value != '1' else '')
        if normalized.endswith('d'):
            value = normalized[:-1]
            return f'{value} day' + ('s' if value != '1' else '')
        return interval

    def _calculate_costs_yahoo(self):
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=self.days)).strftime('%Y-%m-%d')

        data = yf.download(
            self.symbol,
            start=start_date,
            end=end_date,
            interval=self.interval,
            multi_level_index=False
        )

        if data.empty:
            raise ValueError(f'No data available for {self.symbol}')

        data['spread'] = (data['High'] - data['Low']) / data['Close']
        data['hour'] = data.index.hour
        data['date'] = data.index.date

        hourly_avg = data.groupby('hour')['spread'].mean()
        self.hourly_costs = hourly_avg.to_dict()
        daily_avg = data.groupby('date')['spread'].mean()
        self.daily_costs = daily_avg.to_dict()

    def _set_default_costs(self):
        """Set default costs if calculation fails."""
        # Default: 0.0002 (0.02%) for all hours
        self.hourly_costs = {i: 0.0002 for i in range(24)}
        print("Using default trading costs (0.02% spread)")
    
    def get_hourly_cost(self, hour=None):
        """
        Get trading cost for a specific hour.
        
        Parameters
        ----------
        hour : int, optional
            Hour of day (0-23). If None, uses current hour.
        
        Returns
        -------
        float
            Trading cost as percentage of price
        """
        if hour is None:
            hour = datetime.now().hour
        
        # Ensure hour is in valid range
        hour = hour % 24
        
        # Return hourly cost or default
        return self.hourly_costs.get(hour, 0.0002)
    
    def get_average_cost(self):
        """
        Get average trading cost across all hours.
        
        Returns
        -------
        float
            Average trading cost as percentage of price
        """
        if not self.hourly_costs:
            return 0.0002
        
        costs = list(self.hourly_costs.values())
        return sum(costs) / len(costs) if costs else 0.0002
    
    def get_daily_cost(self, date=None):
        """
        Get average trading cost for a specific day.
        
        Parameters
        ----------
        date : datetime.date, optional
            Date to retrieve cost for. If None, uses today.
        
        Returns
        -------
        float
            Average daily trading cost as percentage of price
        """
        if date is None:
            date = datetime.now().date()
        
        return self.daily_costs.get(date, self.get_average_cost())
    
    def get_costs_dataframe(self):
        """
        Get hourly costs as a DataFrame.
        
        Returns
        -------
        pd.DataFrame
            DataFrame with hour and cost columns
        """
        df = pd.DataFrame(
            list(self.hourly_costs.items()),
            columns=['Hour', 'Cost']
        )
        return df.sort_values('Hour')
    
    def print_summary(self):
        """Print summary of calculated trading costs."""
        print(f"\n{'='*50}")
        print(f"Trading Costs Summary for {self.symbol}")
        print(f"{'='*50}")
        print(f"Average Cost: {self.get_average_cost():.6f} ({self.get_average_cost()*100:.4f}%)")
        print(f"\nHourly Costs:")
        print("-" * 50)
        for hour in sorted(self.hourly_costs.keys()):
            cost = self.hourly_costs[hour]
            print(f"  Hour {hour:2d}:00 - {hour:2d}:59: {cost:.6f} ({cost*100:.4f}%)")
        print(f"{'='*50}\n")


# Standalone function for convenience
def get_trading_cost(symbol, hour=None, days=30):
    """
    Get trading cost for a specific symbol and hour.
    
    Parameters
    ----------
    symbol : str
        Ticker symbol
    hour : int, optional
        Hour of day (0-23)
    days : int
        Number of historical days to analyze
    
    Returns
    -------
    float
        Trading cost as percentage
    """
    calculator = TradingCostCalculator(symbol, days=days)
    return calculator.get_hourly_cost(hour)
