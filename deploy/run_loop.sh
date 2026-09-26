#!/usr/bin/env bash
# Runs the bot and restarts it after a crash. A clean shutdown (SIGTERM from bot.sh stop) exits 0 and ends the loop.
cd "$(dirname "${BASH_SOURCE[0]}")/.."
while true; do
  .venv/bin/python -m trading_system.main
  code=$?
  [ "$code" -eq 0 ] && break
  echo "[run_loop $(date '+%Y-%m-%d %H:%M:%S')] bot exited with code $code; restarting in 60s (deploy/bot.sh stop to cancel)"
  sleep 60
done
