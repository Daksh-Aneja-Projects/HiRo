#!/usr/bin/env bash
# wait-for-it.sh - minimal tcp wait helper

set -e

HOST=""
PORT=""
TIMEOUT=15
QUIET=0

usage() {
  echo "Usage: wait-for-it.sh host:port [-t timeout] [-- command args]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    *:* )
      HOST="${1%%:*}"
      PORT="${1#*:}"
      shift 1
      ;;
    -t|--timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    -q|--quiet)
      QUIET=1
      shift 1
      ;;
    --)
      shift
      break
      ;;
    *)
      usage
      ;;
  esac
done

if [[ -z "$HOST" || -z "$PORT" ]]; then
  usage
fi

if [[ $QUIET -ne 1 ]]; then
  echo "⏳ Waiting for $HOST:$PORT (timeout: ${TIMEOUT}s)..."
fi

end_time=$(( $(date +%s) + TIMEOUT ))

while :
do
  if nc -z "$HOST" "$PORT" >/dev/null 2>&1; then
    if [[ $QUIET -ne 1 ]]; then
      echo "✅ $HOST:$PORT is available."
    fi
    break
  fi

  if [[ $(date +%s) -ge $end_time ]]; then
    if [[ $QUIET -ne 1 ]]; then
      echo "❌ Timeout while waiting for $HOST:$PORT."
    fi
    exit 1
  fi

  sleep 1
done

if [[ $# -gt 0 ]]; then
  exec "$@"
fi
