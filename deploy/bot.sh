#!/usr/bin/env bash
# Control the trading bot on the server.
#
#   deploy/bot.sh deploy    install deps, preflight-check, then restart (used by the GitHub Action)
#   deploy/bot.sh start     start the bot in a detached tmux session (or nohup if tmux is missing)
#   deploy/bot.sh stop      graceful stop: SIGTERM, wait for the current step to finish, then kill
#   deploy/bot.sh restart   stop + start
#   deploy/bot.sh status    is it running, which commit, recent log lines
#   deploy/bot.sh logs      follow the log file (Ctrl+C to stop watching; the bot keeps running)
#   deploy/bot.sh attach    attach to the live console (detach with Ctrl+b then d; Ctrl+C there restarts the bot in 60s)
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

SESSION="aistock"
VENV="$APP_DIR/.venv"
PY="$VENV/bin/python"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/trading.log"
CONSOLE_LOG="$LOG_DIR/console.log"
STOP_TIMEOUT="${STOP_TIMEOUT:-300}"   # seconds to let a sweep finish its current ticker
# Matches only the long-running scheduler (no extra args), not one-shot --sweep-only/--report runs.
PROC_PATTERN=' -m trading_system\.main$'

mkdir -p "$LOG_DIR"

log() { echo "[bot.sh $(date '+%Y-%m-%d %H:%M:%S')] $*"; }

have_tmux() { command -v tmux >/dev/null 2>&1; }

bot_pids() { pgrep -f -- "$PROC_PATTERN" || true; }

ensure_venv() {
  if [ ! -x "$PY" ]; then
    local base
    base="$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3)"
    "$base" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
      || { log "Python 3.10+ required (found $("$base" --version))"; exit 1; }
    log "Creating virtualenv with $("$base" --version)"
    "$base" -m venv "$VENV"
  fi
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q -r trading_system/requirements.txt
}

preflight() {
  log "Preflight check"
  "$PY" -m trading_system.main --check
}

stop() {
  # Stop the crash-restart loop first so it can't relaunch the bot (or old code) after we stop it.
  pkill -f -- "$APP_DIR/deploy/run_loop.sh" 2>/dev/null || true
  local pids
  pids="$(bot_pids)"
  if [ -z "$pids" ]; then
    log "Bot is not running"
  else
    log "Sending SIGTERM to $pids; waiting up to ${STOP_TIMEOUT}s for the current step to finish"
    kill -TERM $pids 2>/dev/null || true
    local waited=0
    while [ -n "$(bot_pids)" ] && [ "$waited" -lt "$STOP_TIMEOUT" ]; do
      sleep 2
      waited=$((waited + 2))
    done
    if [ -n "$(bot_pids)" ]; then
      log "Still running after ${STOP_TIMEOUT}s; killing"
      kill -KILL $(bot_pids) 2>/dev/null || true
    fi
    log "Bot stopped"
  fi
  if have_tmux && tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
  fi
}

start() {
  if [ -n "$(bot_pids)" ]; then
    log "Bot already running (pid $(bot_pids))"
    return 0
  fi
  [ -x "$PY" ] || ensure_venv
  # run_loop.sh restarts the bot after a crash, but not after a clean SIGTERM shutdown.
  local loop="$APP_DIR/deploy/run_loop.sh"

  if have_tmux; then
    tmux new-session -d -s "$SESSION" -c "$APP_DIR" "bash '$loop' 2>&1 | tee -a '$CONSOLE_LOG'"
    log "Started in tmux session '$SESSION' (attach: deploy/bot.sh attach)"
  else
    nohup bash "$loop" >> "$CONSOLE_LOG" 2>&1 < /dev/null &
    log "tmux not found; started with nohup (console output: $CONSOLE_LOG)"
  fi

  sleep 5
  if [ -n "$(bot_pids)" ]; then
    log "Bot running (pid $(bot_pids)) at commit $(git rev-parse --short HEAD)"
  else
    log "Bot failed to start; last console output:"
    tail -n 30 "$CONSOLE_LOG" || true
    exit 1
  fi
}

status() {
  echo "Commit:  $(git rev-parse --short HEAD) ($(git log -1 --format=%cd --date=relative))"
  if [ -n "$(bot_pids)" ]; then
    echo "Status:  RUNNING (pid $(bot_pids | tr '\n' ' '))"
  else
    echo "Status:  STOPPED"
  fi
  if have_tmux && tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Console: tmux session '$SESSION' (deploy/bot.sh attach)"
  fi
  echo "--- last 15 log lines ($LOG_FILE) ---"
  tail -n 15 "$LOG_FILE" 2>/dev/null || echo "(no log yet)"
}

case "${1:-}" in
  deploy)  ensure_venv; preflight; stop; start ;;
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  logs)    tail -n 50 -F "$LOG_FILE" ;;
  attach)
    if have_tmux && tmux has-session -t "$SESSION" 2>/dev/null; then
      exec tmux attach -t "$SESSION"
    else
      echo "No tmux session; following console log instead"; exec tail -n 50 -F "$CONSOLE_LOG"
    fi ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
