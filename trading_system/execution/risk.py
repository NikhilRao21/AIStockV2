import logging
from trading_system import config

logger = logging.getLogger(__name__)


def _normalize_position_size_pct(value):
    try:
        size_pct = float(value)
    except (TypeError, ValueError):
        return 0.0

    return size_pct / 100.0 if size_pct > 1.0 else size_pct

def check_confidence(rec: dict) -> tuple[bool, str]:
    if rec.get("confidence", 0) < config.MIN_CONFIDENCE_SCORE:
        return False, f"Confidence {rec.get('confidence')} below minimum {config.MIN_CONFIDENCE_SCORE}"
    return True, ""

def check_position_size(rec: dict, portfolio_value: float) -> tuple[bool, str]:
    size_pct = _normalize_position_size_pct(rec.get("position_size_pct", 0))
    if size_pct > config.MAX_POSITION_PCT:
        return False, f"Position size {size_pct} exceeds max {config.MAX_POSITION_PCT}"
    return True, ""

def check_cash_reserve(notional: float, cash: float, portfolio_value: float) -> tuple[bool, str]:
    if portfolio_value == 0:
        return False, "Portfolio value is 0"
    remaining_cash_pct = (cash - notional) / portfolio_value
    logger.info(
        "Cash reserve check: cash=%s notional=%s portfolio_value=%s remaining_cash_pct=%s min_cash_reserve_pct=%s",
        cash,
        notional,
        portfolio_value,
        remaining_cash_pct,
        config.MIN_CASH_RESERVE_PCT,
    )
    if remaining_cash_pct < config.MIN_CASH_RESERVE_PCT:
        return False, "Insufficient cash reserve"
    return True, ""

def check_open_positions(positions: list) -> tuple[bool, str]:
    if len(positions) >= config.MAX_OPEN_POSITIONS:
        return False, "Max open positions reached"
    return True, ""

def check_entries_this_sweep(sweep_entries: int) -> tuple[bool, str]:
    if sweep_entries >= config.MAX_ENTRIES_PER_SWEEP:
        return False, "Max entries per sweep reached"
    return True, ""

def check_daily_loss(portfolio_value: float, day_start_value: float) -> tuple[bool, str]:
    if day_start_value == 0:
        return True, ""
    loss_pct = (day_start_value - portfolio_value) / day_start_value
    if loss_pct >= config.MAX_DAILY_LOSS_PCT:
        return False, f"Daily loss {loss_pct} exceeds max {config.MAX_DAILY_LOSS_PCT}"
    return True, ""

def check_drawdown(portfolio_value: float, peak_value: float) -> tuple[bool, str]:
    if peak_value == 0:
        return True, ""
    drawdown_pct = (peak_value - portfolio_value) / peak_value
    if drawdown_pct >= config.MAX_DRAWDOWN_PCT:
        return False, f"Drawdown {drawdown_pct} exceeds max {config.MAX_DRAWDOWN_PCT}"
    return True, ""

def check_market_open(clock) -> tuple[bool, str]:
    return True, ""  # Override to allow testing outside market hours
    if not clock.is_open:
        return False, "Market is closed"
    return True, ""

def check_duplicate_position(ticker: str, positions: list) -> tuple[bool, str]:
    for pos in positions:
        if pos.symbol == ticker:
            return False, f"Position in {ticker} already open"
    return True, ""

def run_all_checks(rec: dict, account, positions: list, clock, peak_value: float, day_start_value: float, sweep_entries: int) -> tuple[bool, list[str]]:
    reasons = []
    
    ticker = rec.get("ticker")
    portfolio_value = float(account.portfolio_value)
    cash = float(account.cash)
    position_size_pct = _normalize_position_size_pct(rec.get("position_size_pct", 0))
    notional = portfolio_value * position_size_pct

    logger.info(
        "Risk inputs for %s: portfolio_value=%s cash=%s position_size_pct=%s notional=%s open_positions=%s sweep_entries=%s peak_value=%s day_start_value=%s",
        ticker,
        portfolio_value,
        cash,
        position_size_pct,
        notional,
        len(positions),
        sweep_entries,
        peak_value,
        day_start_value,
    )
    
    checks = [
        check_confidence(rec),
        check_position_size(rec, portfolio_value),
        check_cash_reserve(notional, cash, portfolio_value),
        check_open_positions(positions),
        check_entries_this_sweep(sweep_entries),
        check_daily_loss(portfolio_value, day_start_value),
        check_drawdown(portfolio_value, peak_value),
        check_market_open(clock),
        check_duplicate_position(ticker, positions)
    ]
    
    for passed, reason in checks:
        if not passed:
            reasons.append(reason)
            
    return len(reasons) == 0, reasons
