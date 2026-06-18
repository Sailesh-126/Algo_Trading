# Quick Reference Guide

## Starting the System

```bash
# Run the main orchestrator
python main.py
```

The system will:
1. Read `config.json` to find the active trader and parameters
2. Run the trader continuously
3. On Friday after `end_time`, automatically perform backtest and select best strategy
4. Update `config.json` for next week

---

## Changing Strategies

### Option 1: Manual Configuration
Edit `config.json` and change `active_trader` to one of:
- `"SMAtrader"` - Simple Moving Average
- `"Contrader"` - Contrarian (Mean Reversion)
- `"MLtrader"` - Machine Learning
- `"Bolltrader"` - Bollinger Bands

Example:
```json
{
  "active_trader": "MLtrader",
  "parameters": {
    "lags": 5,
    "units": 1000,
    "freq": "1 min",
    "end_time": "11:21:00"
  }
}
```

### Option 2: Let System Auto-Select
Just run `python main.py` on Friday after `end_time`. The system will:
- Backtest all 4 strategies
- Select the best performer
- Automatically update `config.json`

---

## Parameter Tuning

### SMAtrader Parameters
```json
"parameters": {
  "sma_s": 2,        // Short-term MA period
  "sma_l": 5,        // Long-term MA period
  "units": 1000,     // Trade size
  "freq": "1 min",   // Bar frequency
  "end_time": "11:21:00"  // Trading end time
}
```

### Contrader Parameters
```json
"parameters": {
  "window": 5,       // Mean reversion lookback
  "units": 1000,
  "freq": "1 min",
  "end_time": "11:21:00"
}
```

### MLtrader Parameters
```json
"parameters": {
  "lags": 5,         // Lagged features
  "units": 1000,
  "freq": "1 min",
  "end_time": "11:21:00"
}
```

### BollTrader Parameters
```json
"parameters": {
  "sma": 50,         // Bollinger Bands SMA period
  "dev": 2,          // Standard deviation multiplier
  "units": 1000,
  "freq": "1 min",
  "end_time": "11:21:00"
}
```

---

## Architecture Overview

```
main.py (TradingOrchestrator)
    ├─ ConfigManager
    │   ├─ read_config() → reads config.json
    │   └─ write_config() → saves config.json
    │
    ├─ TraderFactory
    │   └─ create_trader(name, **params) → returns trader instance
    │
    ├─ Trader (runs continuously)
    │   ├─ SMATrader
    │   ├─ ConTrader
    │   ├─ MLTrader
    │   └─ BollTrader
    │
    └─ BacktesterFactory (Friday auto-select)
        ├─ Backtest all 4 strategies
        ├─ Find best performer
        └─ Update config.json for next week
```

---

## Current Status

✅ **Implemented:**
- All traders refactored as parameterized classes
- Main.py orchestrator with auto-selection
- Config.json for trader management
- Weekly backtest automation

⚠️ **To Configure Before Running:**
1. Ensure Interactive Brokers TWS/Gateway is running
2. Use a paper trading account (NEVER live trading)
3. Verify `end_time` matches your trading session
4. Check contract settings (currently EURUSD forex)

---

## Example Workflows

### Workflow 1: Auto-Select Weekly
Monday-Thursday: Run selected strategy  
Friday 11:21:01: System backtests all models  
Friday 11:22:00: config.json updated with best model  
Monday: Run new strategy

### Workflow 2: Manual Testing
Edit config.json → Run new strategy → Observe results → Adjust parameters

### Workflow 3: All-Day Backtest
```python
from Backtesting.SMABackTester import SMABacktester

tester = SMABacktester(
    symbol='EURUSD=X',
    SMA_S=2, SMA_L=5,
    start='2024-01-01', end='2024-06-01',
    interval='1h'
)
perf, outperf = tester.test_strategy()
print(f"Performance: {perf}")
```

---

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Main orchestrator (NEW) |
| `config.json` | Strategy configuration (NEW) |
| `Traders/SMAtrader.py` | SMA strategy (refactored) |
| `Traders/Contrader.py` | Contrarian strategy (refactored) |
| `Traders/MLtrader.py` | ML strategy (refactored) |
| `Traders/Bolltrader.py` | Bollinger Bands (refactored) |
| `Backtesting/*.py` | Backtesting classes (unchanged) |

---

## Support

For detailed documentation, see `README.md`  
For architecture notes, see `/memories/repo/trading_system_architecture.md`
