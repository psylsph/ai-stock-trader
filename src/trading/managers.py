import json
import os
from datetime import datetime
from typing import Optional, List
from src.database.repository import DatabaseRepository
from src.database.models import Position, Stock

class PositionManager:
    def __init__(self, repo: DatabaseRepository, portfolio_file: str = "portfolio.json"):
        self.repo = repo
        self.portfolio_file = portfolio_file

    async def update_position(self, symbol: str, quantity: float, price: float, action: str, balance: Optional[float] = None):
        """Update position in DB after a trade execution"""
        stock = await self.repo.get_or_create_stock(symbol, symbol)
        
        # We need a method in repo to get exact position or we just raw query
        # Since repo is async context manager based, we might need to extend it 
        # or just do the logic here if we can access session, 
        # but repo encapsulates session. Let's add a specialized method to repo or 
        # use get_positions and filter (inefficient but works for now).
        # Better: use repo to get specific position.
        
        # For MVP, we will assume we can fetch all positions and find the one we need.
        # In production, add get_position_by_symbol to Repo.
        
        positions = await self.repo.get_positions()
        target_pos = next((p for p in positions if p.stock.symbol == symbol), None)
        
        async with self.repo.session_maker() as session:
            # We need to re-fetch attached to this session to modify
            if target_pos:
                target_pos = await session.get(Position, target_pos.id)
            
            if action == "BUY":
                if target_pos:
                    # Update average entry price
                    total_cost = (target_pos.quantity * target_pos.entry_price) + (quantity * price)
                    target_pos.quantity += quantity
                    target_pos.entry_price = total_cost / target_pos.quantity
                    target_pos.current_price = price 
                else:
                    target_pos = Position(
                        stock_id=stock.id,
                        quantity=quantity,
                        entry_price=price,
                        current_price=price,
                        unrealized_pnl=0.0
                    )
                    session.add(target_pos)
            
            elif action == "SELL":
                if target_pos:
                    target_pos.quantity -= quantity
                    target_pos.current_price = price
                    if target_pos.quantity <= 0.0001: # Float epsilon
                        await session.delete(target_pos)
            
            await session.commit()
            
        # Print status after update
        await self.display_portfolio(balance)

    async def display_portfolio(self, balance: Optional[float] = None):
        """Print current holdings in a clean format and save to JSON"""
        positions = await self.repo.get_positions()
        
        # Prepare data for JSON
        portfolio_data = {
            "timestamp": datetime.now().isoformat(),
            "cash_balance": balance,
            "total_value": balance or 0,
            "positions": []
        }

        print("\n" + "="*50)
        print(f"{'CURRENT PORTFOLIO STATUS':^50}")
        print("="*50)
        
        if balance is not None:
            print(f"Cash Balance: £{balance:,.2f}")
            print("-" * 50)

        if not positions:
            print("No active positions.")
        else:
            print(f"{'Symbol':<10} | {'Qty':>8} | {'Entry':>10} | {'Current':>10} | {'P&L %':>8}")
            print("-" * 50)
            total_value = balance or 0
            for p in positions:
                pnl_pct = ((p.current_price - p.entry_price) / p.entry_price * 100) if p.entry_price else 0
                print(f"{p.stock.symbol:<10} | {p.quantity:>8.2f} | {p.entry_price:>10.2f} | {p.current_price:>10.2f} | {pnl_pct:>7.1f}%")
                
                pos_value = p.quantity * p.current_price
                total_value += pos_value
                
                portfolio_data["positions"].append({
                    "symbol": p.stock.symbol,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "market_value": round(pos_value, 2)
                })
            
            portfolio_data["total_value"] = round(total_value, 2)
            
            if balance is not None:
                print("-" * 50)
                print(f"{'Total Portfolio Value:':<30} £{total_value:,.2f}")
                
        print("="*50 + "\n")
        
        # Save to JSON
        try:
            with open(self.portfolio_file, 'w') as f:
                json.dump(portfolio_data, f, indent=4)
        except Exception as e:
            print(f"Error saving portfolio JSON: {e}")

class RiskManager:
    def __init__(self, max_position_pct: float = 0.20):
        self.max_position_pct = max_position_pct

    def validate_trade(self, 
                      action: str, 
                      quantity: float, 
                      price: float, 
                      total_portfolio_value: float, 
                      current_position_size: float = 0.0) -> bool:
        """
        Validate if trade meets risk requirements.
        """
        trade_value = quantity * price
        
        if action == "BUY":
            # Check max position size
            projected_size = current_position_size + trade_value
            if projected_size > (total_portfolio_value * self.max_position_pct):
                return False
                
        return True

    def check_stop_loss(self, position: Position, stop_loss_pct: float = 0.05) -> bool:
        """Check if position has hit stop loss"""
        if position.quantity == 0:
            return False
            
        pnl_pct = (position.current_price - position.entry_price) / position.entry_price
        return pnl_pct < -stop_loss_pct
