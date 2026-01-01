# AI Stock Trading Bot (LSE Edition)

An advanced AI-powered stock trading bot designed for the **London Stock Exchange (LSE)**. It utilizes a dual-tier AI architecture to analyze market conditions, monitor positions, and execute trades.

## Key Features

- **Dual AI Architecture**:
  - **Remote AI (OpenRouter/Grok-4)**: Performs deep market analysis, research, and high-level strategy using real-time internet access.
  - **Local AI (LM Studio)**: Efficiently monitors open positions and price action intraday without incurring API costs.
- **Real-Time News Integration**: Fetches and analyzes RSS feeds from **Financial Times** and **Money.com** to inform trading decisions.
- **LSE Optimized**: Built directly for UK stocks (e.g., `LLOY.L`, `BP.L`) with appropriate market hour awareness.
- **Alpha Vantage Integration**: Uses Alpha Vantage API for reliable daily and intraday market data.
- **Paper Trading Engine**: built-in simulator to test strategies risk-free with a virtual portfolio.
- **Risk Management**: Automated position sizing and risk checks (max position size, stop losses).
- **Configurable Prescreening**: Adjust how many stocks pass from technical screening to AI analysis.

## Prerequisites

- **Python 3.10+**
- **LM Studio**: Running locally with a model loaded (e.g., `mistralai/ministral-3-14b-reasoning`).
- **Alpha Vantage API Key**: (Free tier available).
- **OpenRouter API Key**: For remote AI access.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/ai-stock-trader.git
   cd ai-stock-trader
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the environment:**
   Copy the example config and edit it with your keys.

   ```bash
   cp .env.example .env
   ```

    **Edit `.env`:**

    ```bash
    OPENROUTER_API_KEY=your_key_here
    MAX_PRESCREENED_STOCKS=10  # Number of stocks to pass from prescreening to AI analysis
    ```

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `INITIAL_BALANCE` | 1000 | Starting balance for paper trading |
| `MAX_PRESCREENED_STOCKS` | 10 | Number (e.g., "10") or ticker (e.g., "BA.L") - top N stocks or all stocks scoring above the cutoff ticker |
| `OPENROUTER_API_URL` | https://openrouter.ai/api/v1 | OpenRouter endpoint URL (override for custom endpoints) |

### Run the Bot

Start the bot in paper trading mode (default):

```bash
python -m src.main
```

The bot will:

1. **Fetch News**: Summarize top headlines from FT & Money.com.
2. **Startup Analysis**: Use Remote AI to analyze the market & news to generate a strategy.
3. **Monitoring Loop**: Continuously check existing positions using Local AI.
4. **Execute Trades**: Buy/Sell based on AI confidence and Risk Manager validation.

### Run Verification Scripts

- **Verify Alpha Vantage Connection**: `python verify_av.py`
- **Verify News Fetching**: `python verify_news.py`
- **Run Unit Tests**: `pytest`

## Project Structure

- `src/ai/`: AI clients (OpenRouter, Ollama) and Decision Engine.
- `src/market/`: Data fetchers (Alpha Vantage, RSS News).
- `src/trading/`: Paper trader, Position & Risk managers.
- `src/orchestration/`: Main workflows.
- `src/database/`: SQLite models and storage.

## License

MIT
