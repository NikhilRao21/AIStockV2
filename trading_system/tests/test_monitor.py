from trading_system import config
from trading_system.monitor.position_monitor import exit_levels


def test_fixed_levels_without_atr():
    stop, target, trailing = exit_levels(100.0, None, None)
    assert round(stop, 2) == round(100 * (1 - config.STOP_LOSS_PCT), 2)
    assert round(target, 2) == round(100 * (1 + config.TAKE_PROFIT_PCT), 2)
    assert not trailing


def test_atr_stop_trails_high_water():
    stop, target, trailing = exit_levels(100.0, 2.0, 100.0)
    assert stop == 96.0 and target == 108.0 and not trailing
    stop, _, trailing = exit_levels(100.0, 2.0, 106.0)
    assert stop == 102.0 and trailing
