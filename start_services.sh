#!/bin/bash
# Start all Forwardr services

echo "🚀 Starting Forwardr services..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Run: python -m venv .venv"
    exit 1
fi

# Start the FastAPI server in background
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo "  ⚠️  FastAPI server already running"
else
    .venv/bin/python -m uvicorn app.main:app --reload --port 8000 > logs/server.log 2>&1 &
    echo "  ✅ Started FastAPI server (port 8000)"
fi

# Wait up to 15 seconds for server to become healthy
echo "  ⏳ Waiting for server to be ready..."
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Check server health
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  💚 Server is healthy"
    
    # Show enabled platforms
    platforms=$(curl -s http://localhost:8000/health | .venv/bin/python -c "import sys, json; data = json.load(sys.stdin); print(', '.join(data['enabled_platforms']))" 2>/dev/null)
    if [ ! -z "$platforms" ]; then
        echo "  📡 Enabled platforms: $platforms"
    fi
else
    echo "  ❌ Server failed to start (check logs/server.log)"
    exit 1
fi

echo ""
echo "✨ Services started!"
echo ""
echo "Next steps:"
echo "  1. Run Telegram poller: python telegram_poller.py"
echo "  2. Send messages to @f0rwarderrbot on Telegram"
echo "  3. View queue: curl http://localhost:8000/queue | python -m json.tool"
echo ""
echo "To stop: bash stop_services.sh"
