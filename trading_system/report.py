import sqlite3
from trading_system.journal.db import DB_PATH

def generate_report():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            print("--- AI Trading System Report ---")
            
            # Simple stats
            cursor.execute("SELECT count(*) as cnt FROM trades")
            row = cursor.fetchone()
            print(f"Total trades: {row['cnt']}")
            
            cursor.execute("SELECT count(*) as cnt FROM trades WHERE outcome = 'WIN'")
            wins = cursor.fetchone()['cnt']
            print(f"Wins: {wins}")
            
    except Exception as e:
        print(f"Error generating report: {e}")

if __name__ == "__main__":
    generate_report()
