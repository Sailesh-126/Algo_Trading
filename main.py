"""
Main Orchestration Script for Algorithmic Trading
- Reads trader configuration from config.json
- Runs the configured trader
- Every Friday (after end_time), backtests all models and selects the best for next week
"""

import json
import os
from datetime import datetime, timezone, timedelta
import pandas as pd
from pathlib import Path

# =====================================================
# GLOBAL CONFIGURATION VARIABLES
# =====================================================
# Modify these global variables to control trading behavior
GLOBAL_SYMBOL = "AAPL"           # Stock/Forex pair to trade
GLOBAL_UNITS = 1000                  # Trade size in units
GLOBAL_FREQ = "1 min"                # Bar frequency (e.g., "1 min", "5 min", "1h")
GLOBAL_END_TIME = "11:21:00"         # End time for daily trading (HH:MM:SS format)
GLOBAL_BACKTEST_DAYS = 10            # Number of days of historical data for backtesting
GLOBAL_BACKTEST_INTERVAL = "1h"      # Interval for backtesting data (e.g., "1h", "1d")

# =====================================================

# Import trader classes
from Traders.SMAtrader import SMATrader
from Traders.Contrader import ConTrader
from Traders.MLtrader import MLTrader
from Traders.Bolltrader import BollTrader

# Import backtester classes
from Backtesting.SMABackTester import SMABacktester
from Backtesting.ConBackTester import ConBacktester
from Backtesting.MLBackTester import MLBacktester
from Backtesting.MeanRevBackTester import MeanRevBacktester


class ConfigManager:
    """Manages trader configuration."""
    
    CONFIG_FILE = "config.json"
    
    @staticmethod
    def read_config():
        """Read trader configuration from config.json."""
        try:
            with open(ConfigManager.CONFIG_FILE, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return ConfigManager.get_default_config()
    
    @staticmethod
    def write_config(config):
        """Write trader configuration to config.json."""
        with open(ConfigManager.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    @staticmethod
    def get_default_config():
        """Get default configuration."""
        return {
            "active_trader": "SMAtrader",
            "parameters": {
                "sma_s": 2,
                "sma_l": 5,
                "units": GLOBAL_UNITS,
                "freq": GLOBAL_FREQ,
                "end_time": GLOBAL_END_TIME
            }
        }


class TraderFactory:
    """Factory for creating trader instances."""
    
    TRADERS = {
        'SMAtrader': SMATrader,
        'Contrader': ConTrader,
        'MLtrader': MLTrader,
        'Bolltrader': BollTrader,
    }
    
    @staticmethod
    def create_trader(trader_name, **params):
        """Create trader instance from name and parameters."""
        if trader_name not in TraderFactory.TRADERS:
            raise ValueError(f"Unknown trader: {trader_name}")
        
        trader_class = TraderFactory.TRADERS[trader_name]
        return trader_class(**params)


class BacktesterFactory:
    """Factory for creating backtester instances."""
    
    BACKTESTER_CONFIGS = {
        'SMAtrader': {
            'class': SMABacktester,
            'params': {
                'symbol': GLOBAL_SYMBOL,
                'interval': GLOBAL_BACKTEST_INTERVAL,
                'start': (datetime.now() - timedelta(days=GLOBAL_BACKTEST_DAYS)).strftime('%Y-%m-%d'),
                'end': datetime.now().strftime('%Y-%m-%d'),
            },
            'default_params': ['SMA_S', 'SMA_L'],
            'test_params': {
                'SMA_S': range(1, 50, 3),
                'SMA_L': range(50, 500, 5),
            }
        },
        'Contrader': {
            'class': ConBacktester,
            'params': {
                'symbol': GLOBAL_SYMBOL,
                'interval': GLOBAL_BACKTEST_INTERVAL,
                'start': (datetime.now() - timedelta(days=GLOBAL_BACKTEST_DAYS)).strftime('%Y-%m-%d'),
                'end': datetime.now().strftime('%Y-%m-%d'),
            },
            'default_params': ['window'],
            'test_params': {
                'window': range(1, 50),
            }
        },
        'MLtrader': {
            'class': MLBacktester,
            'params': {
                'symbol': GLOBAL_SYMBOL,
                'interval': GLOBAL_BACKTEST_INTERVAL,
                'start': (datetime.now() - timedelta(days=GLOBAL_BACKTEST_DAYS)).strftime('%Y-%m-%d'),
                'end': datetime.now().strftime('%Y-%m-%d'),
            },
            'default_params': [],
            'test_params': {}
        },
        'Bolltrader': {
            'class': MeanRevBacktester,
            'params': {
                'symbol': GLOBAL_SYMBOL,
                'interval': GLOBAL_BACKTEST_INTERVAL,
                'start': (datetime.now() - timedelta(days=GLOBAL_BACKTEST_DAYS)).strftime('%Y-%m-%d'),
                'end': datetime.now().strftime('%Y-%m-%d'),
            },
            'default_params': ['SMA', 'dev'],
            'test_params': {
                'SMA': range(5, 100, 2),
                'dev': range(1, 10),
            }
        },
    }
    
    @staticmethod
    def backtest_trader():
        """Backtest a trader and return its performance."""
        # config = BacktesterFactory.BACKTESTER_CONFIGS.get(trader_name)
        config_params = ConfigManager.read_config.get['parameters']
        if not config_params:
            print(f"No backtester config")
            return None, None
        
        try:
            # BacktesterClass = config['class']
            # base_params = config['params'].copy()
            # test_params = config['test_params'].copy()
            
            # # Create backtester instance
            # backtester = BacktesterClass(**base_params, **test_params)
            
            # # Run strategy
            # perf, outperf = backtester.test_strategy()
            
            # print(f"{trader_name}: Performance = {perf}, Outperformance = {outperf}")
            # return perf, test_params
            performances = {}
            
            symbol = config_params.get('contract')
            symbol = symbol.replace(')', '')
            _, args = symbol.split('(')
            args = args.split(',')
            symbol = args[0].strip(" \'")

            start = datetime.now(timezone.utc) - timedelta(days = 6)
            end = datetime.now(timezone.utc)
            interval = config_params.get('freq')

            parameters = {}

            for tester_class in BacktesterFactory.BACKTESTER_CONFIGS.keys:
                BacktesterClass = BacktesterFactory.BACKTESTER_CONFIGS.get(tester_class).get('class')

                backtester = BacktesterClass(symbol, start, end, interval)

                backtester.optimize_parameters(BacktesterFactory.BACKTESTER_CONFIGS.get('test_params'))
                
                if tester_class == "SMAtrader":
                    parameters[tester_class] = {"sma_s": backtester.sma_s, "sma_l": backtester.sma_l}
                elif tester_class == "MLtrader":
                    parameters[tester_class] = {"lags": backtester.lags}
                elif tester_class == "Contrader":
                    parameters[tester_class] = {"window": backtester.window}
                elif tester_class == "Bolltrader":
                    parameters[tester_class] = {"sma": backtester.sma, "dev": backtester.dev}

                perf, _ = backtester.test_strategy()
                performances[tester_class] = perf

            max_perf = -1000
            final_trader = ''
            for tester in performances.keys:
                if performances[tester] > max_perf:
                    max_perf = performances[tester]
                    final_trader = tester

            parameters["units"] = config_params.get("units")
            parameters["freq"] = interval
            parameters["end_time"] = config_params.get("end_time")
            parameters["contract"] = config_params.get("contract")

            file_to_write = {
                "active_trader": final_trader,
                "parameters": parameters[final_trader]
            }
            ConfigManager.write_config(file_to_write)


        except Exception as e:
            print(f"Error backtesting {tester_class}: {str(e)}")
            return None, None


class TradingOrchestrator:
    """Main orchestrator for trading."""
    
    def __init__(self):
        self.config = ConfigManager.read_config()
        self.trader = None
    
    def run_trader(self):
        """Run the configured trader."""
        trader_name = self.config['active_trader']
        params = self.config['parameters']
        
        print(f"\n{'='*50}")
        print(f"Starting {trader_name} with parameters:")
        print(json.dumps(params, indent=2))
        print(f"{'='*50}\n")
        
        self.trader = TraderFactory.create_trader(trader_name, **params)
        self.trader.run()
    
    def is_friday_after_end_time(self):
        """Check if it's Friday after trading end time."""
        now = datetime.now(timezone.utc)
        end_time_str = self.config['parameters']['end_time']
        
        # Parse end_time
        time_parts = end_time_str.split(':')
        end_hour = int(time_parts[0])
        end_minute = int(time_parts[1])
        end_second = int(time_parts[2]) if len(time_parts) > 2 else 0
        
        is_friday = now.weekday() == 4  # 4 = Friday
        is_after_end_time = now.time() >= datetime.min.time().replace(
            hour=end_hour, minute=end_minute, second=end_second
        )
        
        return is_friday and is_after_end_time
    
    def perform_weekly_backtest(self):
        """Perform weekly backtesting on all models."""
        print("\n" + "="*50)
        print("WEEKLY BACKTEST - Evaluating all models...")
        print("="*50 + "\n")
        
        results = {}
        for trader_name in TraderFactory.TRADERS.keys():
            perf, params = BacktesterFactory.backtest_trader(trader_name)
            if perf is not None:
                results[trader_name] = {'performance': perf, 'parameters': params}
        
        if not results:
            print("No successful backtests. Keeping current configuration.")
            return
        
        # Find best performer
        best_trader = max(results.items(), key=lambda x: x[1]['performance'])
        best_name, best_data = best_trader
        
        print(f"\n{'='*50}")
        print(f"WINNER: {best_name}")
        print(f"Performance: {best_data['performance']}")
        print(f"{'='*50}\n")
        
        # Update configuration
        self.config['active_trader'] = best_name
        self.config['parameters'].update(best_data['parameters'])
        
        # Add extra parameters if needed
        if best_name == 'SMAtrader':
            self.config['parameters'].update({
                'units': GLOBAL_UNITS,
                'freq': GLOBAL_FREQ,
                'end_time': GLOBAL_END_TIME
            })
        elif best_name == 'Contrader':
            self.config['parameters'].update({
                'units': GLOBAL_UNITS,
                'freq': GLOBAL_FREQ,
                'end_time': GLOBAL_END_TIME
            })
        elif best_name == 'MLtrader':
            self.config['parameters'].update({
                'lags': 5,
                'units': GLOBAL_UNITS,
                'freq': GLOBAL_FREQ,
                'end_time': GLOBAL_END_TIME
            })
        elif best_name == 'Bolltrader':
            self.config['parameters'].update({
                'units': GLOBAL_UNITS,
                'freq': GLOBAL_FREQ,
                'end_time': GLOBAL_END_TIME
            })
        
        # Save configuration
        ConfigManager.write_config(self.config)
        print(f"Configuration updated for next week: {json.dumps(self.config, indent=2)}")
    
    def run(self):
        """Main run loop."""
        while True:
            try:
                # Check if it's time for weekly backtest
                if self.is_friday_after_end_time():
                    self.perform_weekly_backtest()
                    # Sleep until next Monday to avoid multiple backtests
                    print("Waiting until next Monday to resume trading...")
                    # Calculate seconds until Monday 9:00 AM
                    now = datetime.now()
                    days_until_monday = (7 - now.weekday()) % 7
                    if days_until_monday == 0:
                        days_until_monday = 7
                    next_monday = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
                    sleep_seconds = (next_monday - now).total_seconds()
                    import time
                    time.sleep(min(sleep_seconds, 3600))  # Sleep max 1 hour at a time
                else:
                    # Run the configured trader
                    self.run_trader()
                    break
            except KeyboardInterrupt:
                print("\nTrading stopped by user.")
                break
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                import traceback
                traceback.print_exc()
                break


if __name__ == "__main__":
    orchestrator = TradingOrchestrator()
    orchestrator.run()
