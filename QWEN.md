# AI Stock Trading Bot (LSE Edition) - Project Context

## Project Overview

The AI Stock Trading Bot is an advanced automated trading system designed specifically for the London Stock Exchange (LSE). It implements a dual-tier AI architecture that combines remote AI for deep market analysis with local AI for efficient position monitoring, enabling sophisticated trading decisions while managing API costs.

### Key Features

- **Dual AI Architecture**:
  - **Remote AI (OpenRouter/Grok-4)**: Performs deep market analysis, research, and high-level strategy using real-time internet access
  - **Local AI (Ollama/Llama 3.2)**: Efficiently monitors open positions and price action intraday without incurring API costs
- **Real-Time News Integration**: Fetches and analyzes RSS feeds from Financial Times and Money.com to inform trading decisions
- **LSE Optimized**: Built directly for UK stocks (e.g., `LLOY.L`, `BP.L`) with appropriate market hour awareness
- **Alpha Vantage Integration**: Uses Alpha Vantage API for reliable daily and intraday market data
- **Paper Trading Engine**: Built-in simulator to test strategies risk-free with a virtual portfolio
- **Risk Management**: Automated position sizing and risk checks (max position size, stop losses)

### Architecture

The project follows a modular architecture with the following key components:

- `src/ai/`: AI clients (OpenRouter, Ollama) and Decision Engine
- `src/market/`: Data fetchers (Alpha Vantage, RSS News)
- `src/trading/`: Paper trader, Position & Risk managers
- `src/orchestration/`: Main workflows
- `src/database/`: SQLite models and storage
- `src/web/`: Web dashboard for monitoring and control

## Building and Running

### Prerequisites

- **Python 3.10+**
- **Ollama**: Installed locally with `llama3.2:3b` model pulled (`ollama pull llama3.2:3b`)
- **Alpha Vantage API Key**: (Free tier available)
- **OpenRouter API Key**: For remote AI access

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ai-stock-trader.git
   cd ai-stock-trader
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the environment:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` with your API keys:
   ```bash
   OPENROUTER_API_KEY=your_key_here
   ```

### Running the Bot

Start the bot in paper trading mode (default):
```bash
python -m src.main
```

Or with web interface:
```bash
python -m src.main --web
```

### Verification Scripts

- **Verify Alpha Vantage Connection**: `python verify_av.py`
- **Verify News Fetching**: `python verify_news.py`
- **Run Unit Tests**: `pytest`

### Docker Deployment

The project includes Docker support with `docker-compose.yml` that sets up both the trading bot and web dashboard services.

## Database Models

The application uses SQLite with SQLAlchemy ORM and includes these key models:

- **Stock**: Represents a stock or ETF with symbol, name, and exchange information
- **Position**: Represents an open trading position with quantity, entry price, and P&L
- **Trade**: Represents a completed trade transaction (buy/sell)
- **MarketSnapshot**: Historical market data points for analysis
- **AIDecision**: Stores AI-generated trading decisions with confidence levels and validation status

## Configuration

The application is configured through environment variables in the `.env` file:

- **AI Configuration**: OpenRouter API key, model selection, LM Studio settings
- **Database**: SQLite connection URL
- **Trading**: Paper vs live mode, check intervals, initial balance, max positions
- **Market Data**: Alpha Vantage API key, RSS feeds for news

## Development Conventions

- The codebase follows Python best practices with type hints
- Async/await patterns are used throughout for non-blocking operations
- Pydantic is used for configuration and data validation
- SQLAlchemy ORM for database operations
- FastAPI for the web dashboard
- Structured logging for debugging and monitoring

## Web Dashboard

The application includes a web dashboard accessible at `http://localhost:8000` when running with the `--web` flag, providing:
- Real-time portfolio monitoring
- Pending trade approval/rejection
- Historical decision tracking
- Position management

## Testing and Validation

The system includes verification scripts for key integrations (Alpha Vantage, news feeds) and follows a paper trading approach for safe testing before live deployment.