import logging
import sys
import os
from datetime import datetime

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = f"logs/trading_{today}.log"
    
    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    
    # Format
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    
    # File Handler
    file_handler = logging.FileHandler(log_file)
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
