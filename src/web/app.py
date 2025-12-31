import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from src.database.repository import DatabaseRepository
from src.database import init_db
from src.config.settings import settings
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Replaces deprecated @app.on_event decorators.
    """
    # Startup: Initialize database if not already set
    if not hasattr(app.state, 'repo') or app.state.repo is None:
        print("[DEBUG] Web server initializing database...")
        app.state.repo = await init_db(settings.DATABASE_URL, reset=False)
        print("[DEBUG] Web server database initialized")
    else:
        print("[DEBUG] Web server using pre-initialized database")
    
    yield
    
    # Shutdown: Close database connections
    if hasattr(app.state, 'repo') and app.state.repo is not None:
        print("[DEBUG] Web server closing database connections...")
        await app.state.repo.close()
        print("[DEBUG] Web server database connections closed")

app = FastAPI(title="AI Stock Trader Dashboard", lifespan=lifespan)
templates = Jinja2Templates(directory="src/web/templates")

def set_repo(r: DatabaseRepository):
    """
    Set the database repository for the app.
    This is used by main.py to pre-initialize the repository before starting the server.
    """
    app.state.repo = r

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not hasattr(app.state, 'repo') or app.state.repo is None:
        raise RuntimeError("Database not initialized")
    positions = await app.state.repo.get_positions()
    pending_decisions = await app.state.repo.get_pending_decisions()
    all_decisions = await app.state.repo.get_all_decisions()

    balance = settings.INITIAL_BALANCE
    portfolio_file = os.getenv("PORTFOLIO_FILE", "portfolio.json")

    if os.path.exists(portfolio_file):
        try:
            with open(portfolio_file, 'r') as f:
                data = json.load(f)
                balance = data.get("cash_balance", balance)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Failed to read portfolio file: {e}")

    total_market_value = sum(p.quantity * p.current_price for p in positions)
    total_value = balance + total_market_value

    latest_decisions = {}
    for decision in sorted(all_decisions, key=lambda d: d.timestamp, reverse=True):
        if decision.symbol not in latest_decisions:
            latest_decisions[decision.symbol] = decision

    return templates.TemplateResponse("index.html", {
        "request": request,
        "positions": positions,
        "pending_decisions": pending_decisions,
        "latest_decisions": latest_decisions,
        "balance": balance,
        "total_value": total_value,
        "total_market_value": total_market_value
    })

@app.get("/api/status")
async def get_status():
    """Get current status with validation results and pending decisions."""
    if not hasattr(app.state, 'repo') or app.state.repo is None:
        raise RuntimeError("Database not initialized")

    positions = await app.state.repo.get_positions()
    pending_decisions = await app.state.repo.get_pending_decisions()
    all_decisions = await app.state.repo.get_all_decisions()

    balance = settings.INITIAL_BALANCE
    portfolio_file = os.getenv("PORTFOLIO_FILE", "portfolio.json")

    if os.path.exists(portfolio_file):
        try:
            with open(portfolio_file, 'r') as f:
                data = json.load(f)
                balance = data.get("cash_balance", balance)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Failed to read portfolio file: {e}")

    total_market_value = sum(p.quantity * p.current_price for p in positions)
    total_value = balance + total_market_value

    latest_decisions = {}
    for decision in sorted(all_decisions, key=lambda d: d.timestamp, reverse=True):
        if decision.symbol not in latest_decisions:
            latest_decisions[decision.symbol] = decision

    latest_decisions_json = {}
    for symbol, d in latest_decisions.items():
        latest_decisions_json[symbol] = {
            "timestamp": d.timestamp.isoformat(),
            "symbol": d.symbol,
            "decision": d.decision,
            "confidence": d.confidence,
            "remote_validation_decision": d.remote_validation_decision,
            "remote_validation_comments": d.remote_validation_comments,
            "executed": d.executed,
            "requires_manual_review": d.requires_manual_review,
            "context": d.context
        }

    return {
        "positions": [
            {
                "symbol": p.stock.symbol,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "pnl_pct": ((p.current_price - p.entry_price) / p.entry_price * 100) if p.entry_price else 0
            } for p in positions
        ],
        "latest_decisions": latest_decisions_json,
        "pending_decisions": [
            {
                "symbol": d.symbol,
                "decision": d.decision,
                "confidence": d.confidence,
                "timestamp": d.timestamp.isoformat(),
                "manual_review_timeout": d.manual_review_timeout.isoformat() if d.manual_review_timeout else None
            } for d in pending_decisions
        ],
        "balance": balance,
        "total_value": total_value,
        "total_market_value": total_market_value,
        "trading_mode": settings.TRADING_MODE
    }

@app.post("/api/trades/{symbol}/approve")
async def approve_trade(symbol: str):
    """Manually approve a pending trade."""
    if not hasattr(app.state, 'repo') or app.state.repo is None:
        raise RuntimeError("Database not initialized")

    await app.state.repo.update_decision_with_validation(
        symbol=symbol,
        remote_validation_decision="MANUAL_APPROVE",
        remote_validation_comments="Approved by user via web interface",
        requires_manual_review=False
    )
    await app.state.repo.mark_decision_executed(symbol)

    return {"status": "approved", "symbol": symbol}

@app.post("/api/trades/{symbol}/reject")
async def reject_trade(symbol: str, reason: str = ""):
    """Manually reject a pending trade."""
    if not hasattr(app.state, 'repo') or app.state.repo is None:
        raise RuntimeError("Database not initialized")

    await app.state.repo.update_decision_with_validation(
        symbol=symbol,
        remote_validation_decision="MANUAL_REJECT",
        remote_validation_comments=f"Rejected by user via web interface: {reason}" if reason else "Rejected by user via web interface",
        requires_manual_review=False
    )

    return {"status": "rejected", "symbol": symbol, "reason": reason}

if __name__ == "__main__":
    import uvicorn

    # Note: Database initialization happens in the lifespan context manager
    # This ensures proper async initialization and cleanup
    uvicorn.run(app, host="0.0.0.0", port=8000)
