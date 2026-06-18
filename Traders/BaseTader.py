"""
Base class for all traders. Provides common interface for executing trading strategies.
"""
from abc import ABC, abstractmethod
import datetime as dt
from ib_async import IB, Forex, MarketOrder
import pandas as pd


class BaseTrader(ABC):
    """Abstract base class for all traders."""
    
    def __init__(self, **params):
        """
        Initialize the trader with parameters.
        
        Parameters
        ----------
        **params : dict
            Strategy-specific parameters (e.g., sma_s, sma_l, units, freq, end_time)
        """
        self.params = params
        self.units = params.get('units', 1000)
        self.freq = params.get('freq', '1 min')
        self.end_time = self._parse_time(params.get('end_time', '11:21:00'))
        self.contract = params.get('contract', Forex('EURUSD'))
        self.ib = None
        self.current_pos = 0
        self.conID = None
        self.df = None
        self.last_bar = None
        
    def _parse_time(self, time_str):
        """Parse time string (HH:MM:SS) to datetime.time object."""
        if isinstance(time_str, dt.time):
            return time_str
        parts = time_str.split(':')
        return dt.time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    
    def connect(self):
        """Connect to IB and qualify contract."""
        self.ib = IB()
        self.ib.connect()
        self.ib.qualifyContracts(self.contract)
        # self.contract = self.contract[0]
        self.conID = self.contract.conId
    
    def disconnect(self):
        """Disconnect from IB."""
        if self.ib:
            self.ib.disconnect()
    
    @abstractmethod
    def generate_signal(self, df):
        """
        Generate trading signal based on strategy.
        
        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with OHLC data
            
        Returns
        -------
        int
            Trading signal (1 for long, -1 for short, 0 for no position)
        """
        pass
    
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
    
    def on_bar_update(self, bars, has_new_bar):
        """Callback for bar updates."""
        if bars[-1].date > self.last_bar:
            self.last_bar = bars[-1].date
            
            # Data Processing
            self.df = pd.DataFrame(bars)[["date", "open", "high", "low", "close"]].iloc[:-1]
            self.df.set_index("date", inplace=True)
            self.df = self.df[["close"]].copy()
            
            # Generate signal
            signal = self.generate_signal(self.df)
            
            # Execute trade
            target = signal * self.units
            self.execute_trade(target=target)
            
            # Display results
            import os
            os.system('cls')
            print(self.df)
