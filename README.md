# Algorithmic Trading System - Complete Implementation

## Overview

This system implements an automated algorithmic trading platform with weekly strategy optimization. It includes:

1. **Four Trading Strategies** (refactored as classes):
   - SMA (Simple Moving Average)
   - Contrarian (Mean Reversion)
   - Machine Learning (Linear Regression)
   - Bollinger Bands

2. **Weekly Backtest & Optimization**:
   - Every Friday after trading hours, all strategies are backtested
   - Best performing strategy is selected for the following week
   - Configuration is automatically updated

3. **Configuration Management**:
   - Centralized `config.json` file stores active trader and parameters
   - Easy to manually override or test different strategies

---

## File Structure

```
algo_trading/
├── main.py                      # Main orchestrator (NEW)
├── config.json                  # Trader configuration (NEW)
│
├── Traders/
│   ├── BaseTader.py            # Base class for traders (NEW)
│   ├── SMAtrader.py            # REFACTORED as class
│   ├── Contrader.py            # REFACTORED as class
│   ├── MLtrader.py             # REFACTORED as class
│   └── Bolltrader.py           # REFACTORED as class
│
└── Backtesting/
    ├── SMABackTester.py        # (Already a class)
    ├── ConBackTester.py        # (Already a class)
    ├── MLBackTester.py         # (Already a class)
    └── MeanRevBackTester.py    # (Already a class)
```

---

## Key Components

### 1. **config.json** - Configuration Management

```json
{
  "active_trader": "SMAtrader",
  "parameters": {
    "sma_s": 2,
    "sma_l": 5,
    "units": 1000,
    "freq": "1 min",
    "end_time": "11:21:00"
  }
}
```

- **active_trader**: Name of the trader class to run
- **parameters**: Strategy-specific parameters passed to the trader

### 2. **Refactored Trader Classes**

All traders follow this structure:

```python
class SMATrader:
    def __init__(self, sma_s=2, sma_l=5, units=1000, freq="1 min", end_time="11:21:00"):
        """Initialize with configurable parameters"""
        
    def connect(self):
        """Connect to Interactive Brokers"""
        
    def generate_signal(self, df):
        """Generate trading signal (-1, 0, or 1)"""
        
    def execute_trade(self, target):
        """Execute trades to reach target position"""
        
    def run(self):
        """Main trading loop"""
```

**Trader Types:**

| Trader | Class | Parameters | Strategy |
|--------|-------|-----------|----------|
| SMA | `SMATrader` | `sma_s`, `sma_l`, `units`, `freq`, `end_time` | SMA crossover |
| Contrarian | `ConTrader` | `window`, `units`, `freq`, `end_time` | Mean reversion |
| ML | `MLTrader` | `lags`, `units`, `freq`, `end_time` | Linear regression on lagged returns |
| Bollinger | `BollTrader` | `sma`, `dev`, `units`, `freq`, `end_time` | Bollinger bands |

### 3. **main.py** - Main Orchestrator

Three main classes:

#### **TradingOrchestrator**
- Main controller for the entire system
- Manages trader execution
- Detects Friday after end_time for backtest
- Coordinates weekly strategy selection

#### **ConfigManager**
```python
ConfigManager.read_config()    # Read config.json
ConfigManager.write_config(config)  # Save config.json
```

#### **TraderFactory**
```python
trader = TraderFactory.create_trader("SMAtrader", sma_s=2, sma_l=5, units=1000)
```

#### **BacktesterFactory**
```python
perf, params = BacktesterFactory.backtest_trader("SMAtrader")
```

---

## How It Works

### Daily Operation

1. **Start the system**:
   ```bash
   python main.py
   ```

2. **System checks the day/time**:
   - If NOT Friday after `end_time`: Run the configured trader from `config.json`
   - If Friday after `end_time`: Perform weekly backtest

3. **Trader runs until end_time**:
   - Generates signals based on strategy
   - Executes trades via Interactive Brokers API
   - Displays results

### Weekly Backtest (Friday after end_time)

1. **Backtest all 4 models** on last 30 days of historical data
2. **Compare performance metrics**:
   ```
   SMAtrader: Performance = 1.0523, Outperformance = 0.0234
   Contrader: Performance = 0.9876, Outperformance = -0.0412
   MLtrader: Performance = 1.1234, Outperformance = 0.0945
   Bolltrader: Performance = 1.0045, Outperformance = -0.0243
   ```
3. **Select best performer** (highest performance value)
4. **Update config.json** with new trader and parameters
5. **Resume trading** with new strategy on Monday

---

## Usage Examples

### Running with Default Configuration

```bash
python main.py
```
Automatically reads `config.json` and runs the configured trader.

### Running a Specific Trader Directly

```python
from Traders.SMAtrader import SMATrader

trader = SMATrader(sma_s=2, sma_l=5, units=1000, freq="1 min", end_time="11:21:00")
trader.run()
```

### Changing Strategy Manually

Edit `config.json`:
```json
{
  "active_trader": "Bolltrader",
  "parameters": {
    "sma": 50,
    "dev": 2,
    "units": 1000,
    "freq": "1 min",
    "end_time": "11:21:00"
  }
}
```

Then run `python main.py` to use the new strategy.

### Testing a Strategy Locally

```python
from Backtesting.SMABackTester import SMABacktester
from datetime import datetime, timedelta

backtester = SMABacktester(
    symbol='EURUSD=X',
    SMA_S=2,
    SMA_L=5,
    start='2024-01-01',
    end='2024-06-01',
    interval='1h'
)
perf, outperf = backtester.test_strategy()
print(f"Performance: {perf}, Outperformance: {outperf}")
```

---

## Configuration Parameters

### Common Parameters (All Traders)

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `units` | int | Position size in units | 1000 |
| `freq` | str | Bar frequency | "1 min", "5 mins", "1 hour" |
| `end_time` | str | Trading session end time | "11:21:00" (HH:MM:SS) |

### Strategy-Specific Parameters

**SMATrader:**
- `sma_s` (int): Short-term SMA period
- `sma_l` (int): Long-term SMA period

**ConTrader:**
- `window` (int): Lookback window for mean reversion

**MLTrader:**
- `lags` (int): Number of lagged features for ML model

**BollTrader:**
- `sma` (int): SMA period for bands
- `dev` (float): Standard deviation multiplier

---

## Important Notes

### Requirements
- **Interactive Brokers**: This system trades live via Interactive Brokers API (ib_async)
- **Python Packages**: pandas, numpy, scikit-learn, yfinance

### Safety Features
- ⚠️ **Paper Trading Only**: Currently configured for paper trading
- ✅ **Auto Close Positions**: All positions are closed at `end_time`
- ✅ **Weekly Optimization**: Prevents overfitting with fresh backtests

### Backtest Data Source
- Historical data from **yfinance** (Yahoo Finance)
- Uses **1-hour bars** for efficiency
- Tests on **last 30 days** of data each Friday

### Future Enhancements
1. Add parameter optimization ranges (e.g., optimize SMA_S from 1-10)
2. Implement walk-forward analysis
3. Add multiple timeframe strategies
4. Implement risk management (stop-loss, max drawdown)
5. Add MongoDB/database for trade logging

---

## Troubleshooting

### **Issue**: "ModuleNotFoundError" when running main.py
**Solution**: Ensure all trader and backtester files are in correct directories and import statements match the folder structure.

### **Issue**: Backtest performance metrics seem off
**Solution**: Check that yfinance returns data correctly. Market hours matter (9:30-16:00 for stocks, 24/5 for forex).

### **Issue**: Trader doesn't execute trades
**Solution**: Ensure Interactive Brokers TWS/Gateway is running and connected. Paper trading account must be active.

---

## System Advantages

✅ **Automated Weekly Selection**: No manual intervention needed  
✅ **Parameterized Traders**: Easy to adjust and test strategies  
✅ **Class-Based Architecture**: Clean, reusable, extensible  
✅ **Central Configuration**: One file controls everything  
✅ **Backtesting Integration**: Results-driven strategy selection  
✅ **Scalable Design**: Easy to add new strategies

---

## Contact & Support

For questions or issues with the implementation, refer to the architecture notes in `/memories/repo/trading_system_architecture.md`
