"""
Dual Strategy Backtester
- Combines two trading strategies using signal strengths
- Calculates weighted position based on signal strengths of both strategies
- Enforces a threshold for combined signal strength before taking trades
- Factors in daily trading costs
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from Utils.TradingCostCalculator import TradingCostCalculator

plt.style.use("seaborn-v0_8")


class DualStrategyBackTester:
    """Class for backtesting dual-strategy combinations with signal strength weighting."""
    
    def __init__(self, symbol, strategy1_params, strategy2_params, 
                 signal_threshold=0.5, start=None, end=None, interval='1h', tc=0):
        """
        Initialize Dual Strategy Backtester.
        
        Parameters
        ----------
        symbol : str
            Ticker symbol to backtest
        strategy1_params : dict
            Parameters for first strategy (type, params dict)
            Example: {'type': 'SMA', 'params': {'SMA_S': 2, 'SMA_L': 5}}
        strategy2_params : dict
            Parameters for second strategy
            Example: {'type': 'MeanRev', 'params': {'window': 5}}
        signal_threshold : float
            Minimum combined signal strength (0-2) required to take trades
            0 = no threshold, 2 = both strategies must fully agree
        start : str, optional
            Start date for backtest
        end : str, optional
            End date for backtest
        interval : str
            Data interval ('1h', '1d', etc.)
        tc : float
            Proportional transaction costs per trade
        """
        self.symbol = symbol
        self.strategy1_params = strategy1_params
        self.strategy2_params = strategy2_params
        self.signal_threshold = signal_threshold
        self.start = start or (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        self.end = end or datetime.now().strftime('%Y-%m-%d')
        self.interval = interval
        self.tc = tc
        self.results = None
        self.trading_costs = None
        
        # Initialize trading cost calculator
        try:
            self.trading_costs = TradingCostCalculator(symbol, days=30, interval=interval)
        except Exception as e:
            print(f"Warning: Could not calculate trading costs: {str(e)}")
        
        self.get_data()
        self.prepare_data()
    
    def __repr__(self):
        s1_str = f"{self.strategy1_params['type']}"
        s2_str = f"{self.strategy2_params['type']}"
        return f"DualStrategyBackTester(symbol={self.symbol}, {s1_str}+{s2_str}, threshold={self.signal_threshold})"
    
    def get_data(self):
        """Download data from yfinance."""
        raw = yf.download(self.symbol, self.start, self.end, 
                         multi_level_index=False, interval=self.interval)
        raw = raw['Close'].to_frame().dropna()
        raw.rename(columns={'Close': 'price'}, inplace=True)
        raw['returns'] = np.log(raw / raw.shift(1))
        raw['hour'] = raw.index.hour  # Store hour for trading costs
        self.data = raw
    
    def prepare_data(self):
        """Prepare data for both strategies."""
        data = self.data.copy()
        
        # Prepare Strategy 1
        if self.strategy1_params['type'] == 'SMA':
            sma_s = self.strategy1_params['params'].get('SMA_S', 2)
            sma_l = self.strategy1_params['params'].get('SMA_L', 5)
            data['SMA_S'] = data['price'].rolling(sma_s).mean()
            data['SMA_L'] = data['price'].rolling(sma_l).mean()
            data['strategy1_raw_signal'] = np.where(data['SMA_S'] > data['SMA_L'], 1, -1)
        
        elif self.strategy1_params['type'] == 'MeanRev':
            window = self.strategy1_params['params'].get('window', 5)
            data['rolling_returns'] = data['returns'].rolling(window).mean()
            data['strategy1_raw_signal'] = np.where(data['rolling_returns'] > 0, -1, 1)
        
        elif self.strategy1_params['type'] == 'BollingerBands':
            sma = self.strategy1_params['params'].get('SMA', 50)
            dev = self.strategy1_params['params'].get('dev', 2)
            data['SMA'] = data['price'].rolling(sma).mean()
            data['Lower'] = data['SMA'] - data['price'].rolling(sma).std() * dev
            data['Upper'] = data['SMA'] + data['price'].rolling(sma).std() * dev
            data['distance'] = data['price'] - data['SMA']
            signal = np.where(data['price'] < data['Lower'], 1, 0)
            signal = np.where(data['price'] > data['Upper'], -1, signal)
            data['strategy1_raw_signal'] = signal
        
        # Prepare Strategy 2
        if self.strategy2_params['type'] == 'SMA':
            sma_s = self.strategy2_params['params'].get('SMA_S', 2)
            sma_l = self.strategy2_params['params'].get('SMA_L', 5)
            data['SMA_S_2'] = data['price'].rolling(sma_s).mean()
            data['SMA_L_2'] = data['price'].rolling(sma_l).mean()
            data['strategy2_raw_signal'] = np.where(data['SMA_S_2'] > data['SMA_L_2'], 1, -1)
        
        elif self.strategy2_params['type'] == 'MeanRev':
            window = self.strategy2_params['params'].get('window', 5)
            data['rolling_returns_2'] = data['returns'].rolling(window).mean()
            data['strategy2_raw_signal'] = np.where(data['rolling_returns_2'] > 0, -1, 1)
        
        elif self.strategy2_params['type'] == 'BollingerBands':
            sma = self.strategy2_params['params'].get('SMA', 50)
            dev = self.strategy2_params['params'].get('dev', 2)
            data['SMA_2'] = data['price'].rolling(sma).mean()
            data['Lower_2'] = data['SMA_2'] - data['price'].rolling(sma).std() * dev
            data['Upper_2'] = data['SMA_2'] + data['price'].rolling(sma).std() * dev
            signal = np.where(data['price'] < data['Lower_2'], 1, 0)
            signal = np.where(data['price'] > data['Upper_2'], -1, signal)
            data['strategy2_raw_signal'] = signal
        
        self.data = data
    
    def calculate_signal_strength(self, signal):
        """
        Convert raw signal (-1, 0, 1) to signal strength (0-1).
        
        Parameters
        ----------
        signal : array-like
            Raw signal values
        
        Returns
        -------
        array-like
            Signal strength values (0-1)
        """
        # Convert -1 to 0, 0 stays 0, 1 stays 1
        # This gives us strength in range [0, 1]
        strength = np.abs(signal)
        return strength
    
    def test_strategy(self):
        """Backtest the dual strategy combination."""
        data = self.data.copy().dropna()
        
        # Calculate signal strengths (0-1 for each strategy)
        data['signal_strength_1'] = self.calculate_signal_strength(data['strategy1_raw_signal'])
        data['signal_strength_2'] = self.calculate_signal_strength(data['strategy2_raw_signal'])
        
        # Combine signals using directional weighting
        # If both agree (same sign), combine their strengths
        # If they disagree (opposite signs), reduce the combined strength
        combined_signal_raw = data['strategy1_raw_signal'] + data['strategy2_raw_signal']
        
        # Position is +1 (long), 0 (no trade), or -1 (short)
        # If combined raw signal is 2 (both +1), position is +1
        # If combined raw signal is -2 (both -1), position is -1
        # If combined raw signal is 0 (both disagree), combined strength < threshold
        data['combined_signal_raw'] = combined_signal_raw
        
        # Calculate combined signal strength (0-2, normalized to 0-1)
        # When both strategies agree: strength = signal_strength_1 + signal_strength_2
        # When they disagree: strength = |difference|
        same_direction = (data['strategy1_raw_signal'] * data['strategy2_raw_signal']) > 0
        data['combined_strength'] = np.where(
            same_direction,
            data['signal_strength_1'] + data['signal_strength_2'],
            np.abs(data['signal_strength_1'] - data['signal_strength_2'])
        )
        
        # Apply threshold: only take position if combined strength meets threshold
        # Normalize threshold to 0-2 range (since strength can be 0-2)
        threshold_normalized = self.signal_threshold * 2
        
        # Determine position based on signal agreement and strength
        data['position'] = np.where(
            data['combined_strength'] >= threshold_normalized,
            np.sign(combined_signal_raw),  # +1, -1, or 0
            0  # No trade if below threshold
        )
        
        # Forward-fill positions to maintain until next signal
        data['position'] = data['position'].replace(0, np.nan)
        data['position'] = data['position'].ffill().fillna(0)
        
        # Calculate trades (position changes)
        data['trades'] = data['position'].diff().fillna(0).abs()
        
        # Apply trading costs (hourly-based)
        hourly_costs = np.zeros(len(data))
        if self.trading_costs:
            for idx, hour in enumerate(data['hour']):
                hourly_costs[idx] = self.trading_costs.get_hourly_cost(int(hour))
        else:
            hourly_costs = np.full(len(data), self.tc)
        
        # Calculate strategy returns = position * returns - trading costs
        data['strategy'] = (data['position'].shift(1) * data['returns'] - 
                           data['trades'] * hourly_costs)
        
        data.dropna(inplace=True)
        
        # Calculate cumulative returns
        data['creturns'] = data['returns'].cumsum().apply(np.exp)
        data['cstrategy'] = data['strategy'].cumsum().apply(np.exp)
        
        self.results = data
        
        # Performance metrics
        perf = data['cstrategy'].iloc[-1] if len(data) > 0 else 0
        outperf = perf - data['creturns'].iloc[-1] if len(data) > 0 else 0
        
        return round(perf, 6), round(outperf, 6)
    
    def plot_results(self):
        """Plot backtest results."""
        if self.results is None:
            print("Run test_strategy() first.")
        else:
            s1 = f"{self.strategy1_params['type']}"
            s2 = f"{self.strategy2_params['type']}"
            title = f"{self.symbol} | {s1} + {s2} (threshold={self.signal_threshold})"
            self.results[["creturns", "cstrategy"]].plot(title=title, figsize=(12, 8))
            plt.show()
    
    def plot_signals(self):
        """Plot individual and combined signals."""
        if self.results is None:
            print("Run test_strategy() first.")
            return
        
        fig, axes = plt.subplots(4, 1, figsize=(14, 10))
        
        # Strategy 1 signal strength
        axes[0].plot(self.results.index, self.results['signal_strength_1'], label='Strategy 1 Strength')
        axes[0].set_ylabel('Signal Strength')
        axes[0].set_title(f"{self.strategy1_params['type']} Signal Strength")
        axes[0].legend()
        
        # Strategy 2 signal strength
        axes[1].plot(self.results.index, self.results['signal_strength_2'], label='Strategy 2 Strength')
        axes[1].set_ylabel('Signal Strength')
        axes[1].set_title(f"{self.strategy2_params['type']} Signal Strength")
        axes[1].legend()
        
        # Combined signal strength
        threshold_line = self.signal_threshold * 2
        axes[2].plot(self.results.index, self.results['combined_strength'], label='Combined Strength')
        axes[2].axhline(y=threshold_line, color='r', linestyle='--', label=f'Threshold ({self.signal_threshold})')
        axes[2].set_ylabel('Combined Strength')
        axes[2].set_title('Combined Signal Strength')
        axes[2].legend()
        
        # Position
        axes[3].plot(self.results.index, self.results['position'], label='Position')
        axes[3].set_ylabel('Position')
        axes[3].set_xlabel('Time')
        axes[3].set_title('Trading Position')
        axes[3].legend()
        
        plt.tight_layout()
        plt.show()
