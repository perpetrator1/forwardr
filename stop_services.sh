#!/bin/bash
# Stop all Forwardr services

echo "🛑 Stopping Forwardr services..."

# Stop the FastAPI server
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    pkill -f "uvicorn app.main:app"
    echo "  ✅ Stopped FastAPI server"
else
    echo "  ℹ️  FastAPI server not running"
fi

# Stop the telegram poller
if pgrep -f "telegram_poller.py" > /dev/null; then
    pkill -f "telegram_poller.py"
    echo "  ✅ Stopped Telegram poller"
else
    echo "  ℹ️  Telegram poller not running"
fi

echo ""
echo "✨ All services stopped!"
