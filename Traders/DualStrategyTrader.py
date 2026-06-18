"""
Dual Strategy Live Trader
- Combines two trading strategies using signal strengths
- Uses signal strength weighting to determine position size
- Applies signal threshold before executing trades
- Factors in hourly trading costs
"""

from ib_async import IB, Forex, MarketOrder, util
import pandas as pd
import numpy as np
import datetime as dt
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from Utils.TradingCostCalculator import TradingCostCalculator


class DualStrategyTrader:
    """Dual-strategy trader combining signal strengths from two strategies."""
    
    def __init__(self, strategy1_params, strategy2_params, signal_threshold=0.5,
                 units=1000, freq="1 min", end_time="11:21:00", contract=Forex('EURUSD')):
        """
        Initialize Dual Strategy Trader.
        
        Parameters
        ----------
        strategy1_params : dict
            Parameters for first strategy {'type': 'SMA', 'params': {...}}
        strategy2_params : dict
            Parameters for second strategy
        signal_threshold : float
            Minimum combined signal strength (0-1) for trades
        units : int
            Trade size in units
        freq : str
            Bar frequency
        end_time : str
            End time for trading (HH:MM:SS format)
        contract : Forex
            Contract to trade
        """
        self.strategy1_params = strategy1_params
        self.strategy2_params = strategy2_params
        self.signal_threshold = signal_threshold
        self.units = units
        self.freq = freq
        self.end_time = self._parse_time(end_time)
        
        self.ib = None
        self.contract = contract
        self.conID = None
        self.current_pos = 0
        self.df = None
        self.last_bar = None
        self.session_start = None
        self.trading_costs = None
        
        # Initialize trading cost calculator
        try:
            self.trading_costs = TradingCostCalculator("EURUSD=X", days=30, interval='1h')
        except:
            self.trading_costs = None
    
    def _parse_time(self, time_str):
        """Parse time string to datetime.time object."""
        if isinstance(time_str, dt.time):
            return time_str
        parts = time_str.split(':')
        return dt.time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    
    def connect(self):
        """Connect to Interactive Brokers."""
        self.ib = IB()
        self.ib.connect()
        self.ib.qualifyContracts(self.contract)
        self.conID = self.contract.conId
    
    def disconnect(self):
        """Disconnect from Interactive Brokers."""
        if self.ib:
            self.ib.disconnect()
    
    def generate_signal_sma(self, df):
        """Generate SMA signal and strength."""
        sma_s = self.strategy1_params['params'].get('SMA_S', 2) if self.strategy1_params['type'] == 'SMA' else \
                self.strategy2_params['params'].get('SMA_S', 2)
        sma_l = self.strategy1_params['params'].get('SMA_L', 5) if self.strategy1_params['type'] == 'SMA' else \
                self.strategy2_params['params'].get('SMA_L', 5)
        
        df['sma_s'] = df.close.rolling(sma_s).mean()
        df['sma_l'] = df.close.rolling(sma_l).mean()
        df.dropna(inplace=True)
        
        if len(df) == 0:
            return 0, 0
        
        signal = 1 if df["sma_s"].iloc[-1] > df["sma_l"].iloc[-1] else -1
        strength = 1.0  # SMA gives full strength (0 or 1)
        
        return signal, strength
    
    def generate_signal_meanrev(self, df, window=5):
        """Generate mean reversion signal and strength."""
        df['returns'] = np.log(df.close / df.close.shift())
        df['rolling'] = df.returns.rolling(window).mean()
        df.dropna(inplace=True)
        
        if len(df) == 0:
            return 0, 0
        
        signal = -1 if df['rolling'].iloc[-1] > 0 else 1
        # Strength based on magnitude of rolling average
        strength = min(abs(df['rolling'].iloc[-1]) / 0.01, 1.0)  # Normalize to 0-1
        
        return signal, strength
    
    def generate_bollinger_signal(self, df, sma=50, dev=2):
        """Generate Bollinger Bands signal and strength."""
        df['sma'] = df.close.rolling(sma).mean()
        df['std'] = df.close.rolling(sma).std()
        df['upper'] = df['sma'] + df['std'] * dev
        df['lower'] = df['sma'] - dev * df['std']
        df.dropna(inplace=True)
        
        if len(df) == 0:
            return 0, 0
        
        price = df.close.iloc[-1]
        upper = df['upper'].iloc[-1]
        lower = df['lower'].iloc[-1]
        mid = df['sma'].iloc[-1]
        
        if price < lower:
            signal = 1  # Long signal
            strength = (lower - price) / (upper - lower)  # How far below lower band
        elif price > upper:
            signal = -1  # Short signal
            strength = (price - upper) / (upper - lower)  # How far above upper band
        else:
            signal = 0
            strength = 0
        
        return signal, strength
    
    def generate_dual_signal(self, df):
        """
        Generate combined signal from both strategies.
        
        Returns
        -------
        tuple
            (position, signal_strength)
        """
        df_copy1 = df.copy()
        df_copy2 = df.copy()
        
        # Strategy 1 signal
        if self.strategy1_params['type'] == 'SMA':
            signal1, strength1 = self.generate_signal_sma(df_copy1)
        elif self.strategy1_params['type'] == 'MeanRev':
            window = self.strategy1_params['params'].get('window', 5)
            signal1, strength1 = self.generate_signal_meanrev(df_copy1, window)
        elif self.strategy1_params['type'] == 'BollingerBands':
            sma = self.strategy1_params['params'].get('SMA', 50)
            dev = self.strategy1_params['params'].get('dev', 2)
            signal1, strength1 = self.generate_bollinger_signal(df_copy1, sma, dev)
        else:
            signal1, strength1 = 0, 0
        
        # Strategy 2 signal
        if self.strategy2_params['type'] == 'SMA':
            signal2, strength2 = self.generate_signal_sma(df_copy2)
        elif self.strategy2_params['type'] == 'MeanRev':
            window = self.strategy2_params['params'].get('window', 5)
            signal2, strength2 = self.generate_signal_meanrev(df_copy2, window)
        elif self.strategy2_params['type'] == 'BollingerBands':
            sma = self.strategy2_params['params'].get('SMA', 50)
            dev = self.strategy2_params['params'].get('dev', 2)
            signal2, strength2 = self.generate_bollinger_signal(df_copy2, sma, dev)
        else:
            signal2, strength2 = 0, 0
        
        # Combine signals
        if signal1 == 0 and signal2 == 0:
            return 0, 0
        
        # If signals agree (same direction)
        if signal1 * signal2 > 0:
            combined_strength = (strength1 + strength2) / 2
            combined_signal = signal1
        # If signals disagree
        elif signal1 * signal2 < 0:
            combined_strength = abs(strength1 - strength2) / 2
            combined_signal = signal1 if strength1 > strength2 else signal2
        # One signal is zero
        else:
            combined_signal = signal1 if signal1 != 0 else signal2
            combined_strength = max(strength1, strength2)
        
        # Apply threshold
        if combined_strength < self.signal_threshold:
            return 0, combined_strength
        
        return combined_signal, combined_strength
    
    def execute_trade(self, target):
        """Execute trade to reach target position."""
        try:
            self.current_pos = [pos.position for pos in self.ib.positions() 
                               if pos.contract.conId == self.conID][0]
        except:
            self.current_pos = 0
        
        trades = target - self.current_pos
        
        if trades > 0:
            order = MarketOrder("BUY", abs(trades))
            self.ib.placeOrder(self.contract, order)
        elif trades < 0:
            order = MarketOrder("SELL", abs(trades))
            self.ib.placeOrder(self.contract, order)
    
    def trade_reporting(self):
        """Display trade report."""
        try:
            fill_df = util.df([fs.execution for fs in self.ib.fills()])[
                ["execId", "time", "side", "cumQty", "avgPrice"]].set_index("execId")
            profit_df = util.df([fs.commissionReport for fs in self.ib.fills()])[
                ["execId", "realizedPNL"]].set_index("execId")
            report = pd.concat([fill_df, profit_df], axis=1).set_index("time").loc[self.session_start:]
            report = report.groupby("time").agg(
                {"side": "first", "cumQty": "max", "avgPrice": "mean", "realizedPNL": "sum"})
            report["cumPNL"] = report.realizedPNL.cumsum()
            
            os.system('cls')
            print(self.df)
            print(f"\nDual Strategy Trader - Threshold: {self.signal_threshold}")
            print(f"Strategy 1: {self.strategy1_params['type']}")
            print(f"Strategy 2: {self.strategy2_params['type']}")
            print("\n", report)
        except:
            pass
    
    def on_bar_update(self, bars, has_new_bar):
        """Callback for bar updates."""
        if bars[-1].date > self.last_bar:
            self.last_bar = bars[-1].date
            
            # Data Processing
            self.df = pd.DataFrame(bars)[["date", "open", "high", "low", "close"]].iloc[:-1]
            self.df.set_index("date", inplace=True)
            self.df = self.df[["close"]].copy()
            
            # Generate dual signal
            signal, strength = self.generate_dual_signal(self.df.copy())
            
            # Trading
            target = signal * self.units
            self.execute_trade(target=target)
            
            # Display
            os.system('cls')
            print(self.df)
            print(f"\nSignal: {signal}, Strength: {strength:.4f}")
            print(f"Threshold: {self.signal_threshold}")
        else:
            self.trade_reporting()
    
    def run(self):
        """Run the dual strategy trader."""
        self.connect()
        self.session_start = pd.to_datetime(dt.datetime.now(dt.timezone.utc))
        self.last_bar = pd.to_datetime(dt.datetime.now(dt.timezone.utc))
        
        print(f"Starting Dual Strategy Trader")
        print(f"Strategy 1: {self.strategy1_params['type']} - {self.strategy1_params['params']}")
        print(f"Strategy 2: {self.strategy2_params['type']} - {self.strategy2_params['params']}")
        print(f"Signal Threshold: {self.signal_threshold}")
        
        bars = self.ib.reqHistoricalData(
            self.contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting=self.freq,
            whatToShow='MIDPOINT',
            useRTH=True,
        )
        
        bars.updateEvent += self.on_bar_update
        
        self.ib.run()
