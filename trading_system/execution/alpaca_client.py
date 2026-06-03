import os
import logging
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

logger = logging.getLogger(__name__)

def get_trading_client() -> TradingClient:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    
    if not api_key or not secret_key:
        raise RuntimeError("Alpaca API keys not found in environment.")
        
    client = TradingClient(api_key, secret_key, paper=True)
    return client

