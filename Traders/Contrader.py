
"""
Contrarian (Mean Reversion) Trading Strategy
Generates trading signals based on mean reversion of returns.
"""
from ib_async import IB, Forex, MarketOrder, util
import pandas as pd
import numpy as np
import datetime as dt
import os


class ConTrader:
    """Contrarian trading strategy class."""
    
    def __init__(self, window=5, units=1000, freq="1 min", end_time="11:21:00", contract = Forex("EURUSD")):
        """
        Initialize Contrarian Trader.
        
        Parameters
        ----------
        window : int
            Rolling window for mean reversion calculation
        units : int
            Trade size in units
        freq : str
            Bar frequency
        end_time : str
            End time for trading (HH:MM:SS format)
        """
        self.window = window
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
        """Generate trading signal based on mean reversion."""
        df["returns"] = np.log(df.close / df.close.shift())
        df["rolling"] = df.returns.rolling(self.window).mean()
        df.dropna(inplace=True)
        
        if len(df) == 0:
            return 0
        
        position = -1 if df["rolling"].iloc[-1] > 0 else 1
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
        """Run the Contrarian trading strategy."""
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
                except Exception:
                    pass
                print("Session Stopped.")
                self.disconnect()
                break


# if __name__ == "__main__":
#     trader = ConTrader(window=5, units=1000, freq="1 min", end_time="11:21:00")
#     trader.run()
# def execute_trade(target):
#     global current_pos
    
#     # 1. get current Position
#     try:
#         current_pos = [pos.position for pos in ib.positions() if pos.contract.conId == conID][0]
#     except:
#         current_pos = 0
         
#     # 2. identify required trades
#     trades = target - current_pos
        
#     # 3. trade execution
#     if trades > 0:
#         side = "BUY"
#         order = MarketOrder(side, abs(trades))
#         trade = ib.placeOrder(contract, order)  
#     elif trades < 0:
#         side = "SELL"
#         order = MarketOrder(side, abs(trades))
#         trade = ib.placeOrder(contract, order)
#     else:
#         pass

# def trade_reporting():
#     global report
    
#     fill_df = util.df([fs.execution for fs in ib.fills()])[["execId", "time", "side", "cumQty", "avgPrice"]].set_index("execId")
#     profit_df = util.df([fs.commissionReport for fs in ib.fills()])[["execId", "realizedPNL"]].set_index("execId")
#     report = pd.concat([fill_df, profit_df], axis = 1).set_index("time").loc[session_start:]
#     report = report.groupby("time").agg({"side":"first", "cumQty":"max", "avgPrice":"mean", "realizedPNL":"sum"})
#     report["cumPNL"] = report.realizedPNL.cumsum()
        
#     os.system('cls')
#     print(df, report)
    
# if __name__ == "__main__": # if you run trader.py as python script
#     # start trading session
#     session_start = pd.to_datetime(datetime.now(timezone.utc))# new
#     bars = ib.reqHistoricalData(
#             contract,
#             endDateTime='',
#             durationStr='1 D',
#             barSizeSetting=freq,
#             whatToShow='MIDPOINT',
#             useRTH=True,
#             formatDate=2,
#             keepUpToDate=True)
#     last_bar = bars[-1].date
#     bars.updateEvent += onBarUpdate
#     ib.sleep(30) # new - to be added (optional)

#     # stop trading session
#     while True:
#         ib.sleep(5) # check every 5 seconds
#         if datetime.now(timezone.utc).time() >= end_time: # if stop conditions has been met
#             execute_trade(target = 0) # close open position 
#             ib.cancelHistoricalData(bars) # stop stream
#             ib.sleep(10)
#             try:
#                 trade_reporting() # final reporting
#             except:
#                 pass
#             print("Session Stopped.")
#             ib.disconnect()
#             break
#         else:
#             pass