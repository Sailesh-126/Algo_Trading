
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
import sys
from pathlib import Path
plt.style.use("seaborn-v0_8")

# Import trading cost calculator
sys.path.insert(0, str(Path(__file__).parent.parent))
from Utils.TradingCostCalculator import TradingCostCalculator


class ConBacktester():
    ''' Class for the vectorized backtesting of simple contrarian trading strategies.
    '''    
    
    def __init__(self, symbol, start, end, window = 5, interval = '1h', tc = 0):
        '''
        Parameters
        ----------
        symbol: str
            ticker symbol (instrument) to be backtested
        start: str
            start date for data import
        end: str
            end date for data import
        tc: float
            proportional transaction/trading costs per trade
        '''
        self.symbol = symbol
        self.start = start
        self.end = end
        self.tc = tc
        self.window = window
        self.interval = interval
        self.results = None
        
        # Initialize trading cost calculator
        try:
            self.trading_costs = TradingCostCalculator(symbol, days=30, interval=interval)
        except Exception as e:
            print(f"Warning: Could not calculate trading costs: {str(e)}")
            self.trading_costs = None
            
        self.get_data()
        
    def __repr__(self):
        return "ConBacktester(symbol = {}, start = {}, end = {})".format(self.symbol, self.start, self.end)
        
    def get_data(self):
        ''' Imports the data from intraday_pairs.csv (source can be changed).
        '''
        raw = yf.download(self.symbol, self.start, self.end, multi_level_index=False, interval = self.interval)
        raw = raw["Close"].to_frame().dropna()
        raw.rename(columns={"Close": "price"}, inplace=True)
        raw["returns"] = np.log(raw / raw.shift(1))
        raw["hour"] = raw.index.hour  # Add hour for trading cost lookup
        self.data = raw
        
    def test_strategy(self):
        ''' Backtests the simple contrarian trading strategy.
        
        Parameters
        ----------
        window: int
            time window (number of bars) to be considered for the strategy.
        '''
        data = self.data.copy().dropna()
        data["position"] = -np.sign(data["returns"].rolling(self.window).mean())
        data["strategy"] = data["position"].shift(1) * data["returns"]
        data.dropna(inplace=True)
        
        # determine the number of trades in each bar
        data["trades"] = data.position.diff().fillna(0).abs()
        
        # Apply hourly trading costs
        hourly_costs = np.zeros(len(data))
        if self.trading_costs:
            for idx, hour in enumerate(data['hour']):
                hourly_costs[idx] = self.trading_costs.get_hourly_cost(int(hour))
        else:
            hourly_costs = np.full(len(data), self.tc)
        
        # subtract transaction/trading costs from pre-cost return
        data.strategy = data.strategy - data.trades * hourly_costs
        
        data["creturns"] = data["returns"].cumsum().apply(np.exp)
        data["cstrategy"] = data["strategy"].cumsum().apply(np.exp)
        self.results = data
        
        perf = data["cstrategy"].iloc[-1] # absolute performance of the strategy
        outperf = perf - data["creturns"].iloc[-1] # out-/underperformance of strategy
        
        return round(perf, 6), round(outperf, 6)
    
    def plot_results(self):
        ''' Plots the performance of the trading strategy and compares to "buy and hold".
        '''
        if self.results is None:
            print("Run test_strategy() first.")
        else:
            title = "{} | Window = {} | TC = {}".format(self.symbol, self.window, self.tc)
            self.results[["creturns", "cstrategy"]].plot(title=title, figsize=(12, 8))
            
    def optimize_parameter(self, window_range):
        ''' Finds the optimal strategy (global maximum) given the window parameter range.

        Parameters
        ----------
        window_range: tuple
            tuples of the form (start, end, step size)
        '''
        
        windows = range(*window_range)
            
        results = []
        for window in windows:
            results.append(self.test_strategy(window)[0])
        
        best_perf = np.max(results) # best performance
        opt = windows[np.argmax(results)] # optimal parameter
        
        # run/set the optimal strategy
        self.window = opt
        self.test_strategy(opt)
        
        # create a df with many results
        many_results =  pd.DataFrame(data = {"window": windows, "performance": results})
        self.results_overview = many_results
        
        return opt, best_perf
                               
        