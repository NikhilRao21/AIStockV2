import logging
import signal
import threading

logger = logging.getLogger(__name__)

_stop = threading.Event()


def install_handlers():
    """SIGTERM (sent by deploy/bot.sh) asks the bot to finish its current step and exit cleanly."""
    def handle(signum, frame):
        logger.info("Received signal %s; shutting down after the current step", signum)
        _stop.set()
    signal.signal(signal.SIGTERM, handle)


def requested() -> bool:
    return _stop.is_set()


def wait(seconds: float) -> bool:
    """Sleep up to `seconds`, returning early (True) if shutdown was requested."""
    return _stop.wait(seconds)
