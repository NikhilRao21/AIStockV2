import logging
import math
from datetime import datetime

from trading_system.journal import db

logger = logging.getLogger(__name__)

BENCHMARK = "SPY"


def compute_stats() -> dict:
    """Realized-trade and equity-curve statistics from the journal."""
    trades = db.get_closed_trades()
    returns = [t["pnl_pct"] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gross_win = sum(t["pnl"] or 0 for t in trades if (t["pnl"] or 0) > 0)
    gross_loss = -sum(t["pnl"] or 0 for t in trades if (t["pnl"] or 0) < 0)

    stats = {
        "closed_trades": len(trades),
        "win_rate": round(len(wins) / len(returns), 3) if returns else None,
        "avg_win_pct": round(sum(wins) / len(wins), 4) if wins else None,
        "avg_loss_pct": round(sum(losses) / len(losses), 4) if losses else None,
        "expectancy_pct": round(sum(returns) / len(returns), 4) if returns else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "realized_pnl": round(sum(t["pnl"] or 0 for t in trades), 2),
        "exits_by_reason": {},
    }
    for t in trades:
        reason = t.get("closed_by") or "unknown"
        stats["exits_by_reason"][reason] = stats["exits_by_reason"].get(reason, 0) + 1

    snapshots = db.get_portfolio_snapshots()
    if len(snapshots) >= 2:
        equity = [s["equity"] for s in snapshots]
        peak, max_dd = equity[0], 0.0
        for value in equity:
            peak = max(peak, value)
            max_dd = max(max_dd, (peak - value) / peak if peak else 0.0)
        # Daily returns from the last snapshot of each day
        daily: dict[str, float] = {}
        for s in snapshots:
            daily[s["recorded_at"][:10]] = s["equity"]
        closes = list(daily.values())
        daily_returns = [b / a - 1 for a, b in zip(closes[:-1], closes[1:]) if a]
        stats.update({
            "start": snapshots[0]["recorded_at"][:10],
            "total_return": round(equity[-1] / equity[0] - 1, 4) if equity[0] else None,
            "max_drawdown": round(max_dd, 4),
        })
        if len(daily_returns) >= 5:
            mean = sum(daily_returns) / len(daily_returns)
            std = math.sqrt(sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1))
            stats["sharpe_annualized"] = round(mean / std * math.sqrt(252), 2) if std else None
    return stats


def benchmark_return(start: str) -> float | None:
    try:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from trading_system.data import market
        bars = market.get_historical_client().get_stock_bars(StockBarsRequest(
            symbol_or_symbols=BENCHMARK, timeframe=TimeFrame.Day, start=datetime.fromisoformat(start),
        )).data.get(BENCHMARK, [])
        return round(float(bars[-1].close) / float(bars[0].open) - 1, 4) if bars else None
    except Exception as e:
        logger.warning("Benchmark lookup failed: %s", e)
        return None


def generate_report():
    stats = compute_stats()
    print("--- AI Trading System Report ---")
    for key, value in stats.items():
        print(f"{key:>20}: {value}")
    if stats.get("start"):
        print(f"{BENCHMARK + ' return':>20}: {benchmark_return(stats['start'])}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    generate_report()
