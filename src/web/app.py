from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from src.database.repository import DatabaseRepository
from src.config import settings
import os

app = FastAPI(title="AI Stock Trader Dashboard")
templates = Jinja2Templates(directory="src/web/templates")

# Global repository instance to be set at startup
repo: DatabaseRepository = None

def set_repo(r: DatabaseRepository):
    global repo
    repo = r

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    positions = await repo.get_positions()
    pending_decisions = await repo.get_pending_decisions()
    all_decisions = await repo.get_all_decisions()
    
    # We'll need a way to get the current balance. 
    # For now, we'll read it from the portfolio.json if it exists, or use initial balance
    balance = settings.INITIAL_BALANCE
    portfolio_file = os.getenv("PORTFOLIO_FILE", "portfolio.json")
    
    import json
    if os.path.exists(portfolio_file):
        try:
            with open(portfolio_file, 'r') as f:
                data = json.load(f)
                balance = data.get("cash_balance", balance)
        except:
            pass

    total_market_value = sum(p.quantity * p.current_price for p in positions)
    total_value = balance + total_market_value

    return templates.TemplateResponse("index.html", {
        "request": request,
        "positions": positions,
        "pending_decisions": pending_decisions,
        "all_decisions": all_decisions,
        "balance": balance,
        "total_value": total_value,
        "total_market_value": total_market_value
    })

@app.get("/api/status")
async def get_status():
    positions = await repo.get_positions()
    return {
        "positions": [
            {
                "symbol": p.stock.symbol,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "pnl_pct": ((p.current_price - p.entry_price) / p.entry_price * 100) if p.entry_price else 0
            } for p in positions
        ]
    }
