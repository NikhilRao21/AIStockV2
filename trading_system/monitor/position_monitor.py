import logging
import time
from datetime import datetime
from trading_system import config
from trading_system.execution import alpaca_client
from trading_system.journal import db

logger = logging.getLogger(__name__)

def run_monitor():
    logger.info("Starting monitor loop")
    try:
        trading_client = alpaca_client.get_trading_client()
        positions = trading_client.get_all_positions()
        account = trading_client.get_account()
        
        # PNL summary
        pnl = float(account.unrealized_pl)
        logger.info(f"Monitor: Portfolio Value: {account.portfolio_value}, Unrealized P&L: {pnl}")
        
        for pos in positions:
            unrealized_plpc = float(pos.unrealized_plpc)
            logger.debug(f"Position {pos.symbol}: PLPC {unrealized_plpc}")
            
            close_reason = None
            if unrealized_plpc <= -config.STOP_LOSS_PCT:
                close_reason = "stop_loss"
            elif unrealized_plpc >= config.TAKE_PROFIT_PCT:
                close_reason = "take_profit"
                
            if close_reason:
                logger.info(f"Closing {pos.symbol} due to {close_reason} ({unrealized_plpc})")
                try:
                    trading_client.close_position(pos.symbol)
                    
                    # Update DB (mock updating trades table)
                    # Note: we need the trade_id to update, but we'll mock it for now.
                    # We would typically get trade_id from the pos or DB matching by ticker and open status
                except Exception as e:
                    logger.error(f"Failed to close {pos.symbol}: {e}")
                    
        # Update snapshots
        db.insert_portfolio_snapshot({
            "recorded_at": datetime.now().isoformat(),
            "portfolio_value": float(account.portfolio_value),
            "cash": float(account.cash),
            "equity": float(account.equity),
            "peak_value": max(float(account.portfolio_value), db.get_peak_value()),
            "open_positions": len(positions),
            "daily_pnl": float(account.unrealized_pl) # Approx
        })
        
    except Exception as e:
        logger.error(f"Monitor loop failed: {e}")

