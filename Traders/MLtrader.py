
"""
Machine Learning (Linear Regression) Trading Strategy
Generates trading signals using ML predictions based on lagged returns.
"""
from ib_async import IB, Forex, MarketOrder, util
import pandas as pd
import numpy as np
import datetime as dt
from sklearn.linear_model import LinearRegression
import os


class MLTrader:
    """Machine Learning trading strategy class."""
    
    def __init__(self, lags=5, units=1000, freq="1 min", end_time="11:21:00", contract = Forex('EURUSD')):
        """
        Initialize ML Trader.
        
        Parameters
        ----------
        lags : int
            Number of lagged features
        units : int
            Trade size in units
        freq : str
            Bar frequency
        end_time : str
            End time for trading (HH:MM:SS format)
        """
        self.lags = lags
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
        self.lm = LinearRegression()
        
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
        # self.contract = Forex('EURUSD')
        self.ib.qualifyContracts(self.contract)
        # self.contract = self.contract[0]
        self.conID = self.contract.conId
    
    def disconnect(self):
        """Disconnect from Interactive Brokers."""
        if self.ib:
            self.ib.disconnect()
    
    def generate_signal(self, df):
        """Generate trading signal based on ML predictions."""
        df["returns"] = np.log(df.close / df.close.shift())
        
        feature_columns = []
        for lag in range(1, self.lags + 1):
            col = f"lag{lag}"
            df[col] = df["returns"].shift(lag)
            feature_columns.append(col)
        
        df.dropna(inplace=True)
        
        if len(df) == 0:
            return 0
        
        mu = df[feature_columns].mean()
        std = df[feature_columns].std()
        df[feature_columns] = (df[feature_columns] - mu) / std
        
        self.lm.fit(df[feature_columns], df["returns"])
        positions = np.sign(self.lm.predict(df[feature_columns]))
        
        position = int(positions[-1]) if positions[-1] != 0 else 0
        return position
    
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
            
            # Generate signal
            signal = self.generate_signal(self.df.copy())
            
            # Trading
            target = signal * self.units
            self.execute_trade(target=target)
            
            # Display
            os.system('cls')
            print(self.df)
        else:
            self.trade_reporting()
    
    def run(self):
        """Run the ML trading strategy."""
        self.connect()
        self.session_start = pd.to_datetime(dt.datetime.now(dt.timezone.utc))
        self.last_bar = pd.to_datetime(dt.datetime.now(dt.timezone.utc))
        
        bars = self.ib.reqHistoricalData(
            self.contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting=self.freq,
            whatToShow='MIDPOINT',
            useRTH=True,
            formatDate=2,
            keepUpToDate=True)
        
        self.last_bar = bars[-1].date
        bars.updateEvent += self.on_bar_update
        self.ib.sleep(30)
        
        # stop trading session
        while True:
            self.ib.sleep(5)
            if dt.datetime.now(dt.timezone.utc).time() >= self.end_time:
                self.execute_trade(target=0)
                self.ib.cancelHistoricalData(bars)
                self.ib.sleep(10)
                try:
                    self.trade_reporting()
                except:
                    pass
                print("Session Stopped.")
                self.disconnect()
                break


if __name__ == "__main__":
    # Example usage
    trader = MLTrader(lags=5, units=1000, freq="1 min", end_time="11:21:00")
    trader.run()
