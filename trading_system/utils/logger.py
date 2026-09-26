import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    log_file = "logs/trading.log"
    
    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    
    # Format
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    
    # File Handler: rotates at midnight so a long-running process doesn't write one giant file
    file_handler = TimedRotatingFileHandler(log_file, when="midnight", backupCount=30)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Avoid duplicate handlers
    if not root.handlers:
        root.addHandler(file_handler)
        root.addHandler(console_handler)
    # Third-party HTTP debug logs drown out our own
    for noisy in ("urllib3", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
