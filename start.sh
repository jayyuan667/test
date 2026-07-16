#!/bin/bash
# Start both frontend and backend
cd "$(dirname "$0")"

echo "🚀 Starting FORGE development environment..."
echo ""

# Start backend on port 5390
echo "📦 Starting backend on port 5390..."
./.venv/bin/python -m backend.app &
BACKEND_PID=$!

# Wait for backend
sleep 2

# Start frontend on port 3002. Webpack avoids a Next 16 Turbopack panic that
# otherwise forces the browser into an endless Fast Refresh reload loop.
echo "🎨 Starting frontend on port 3002..."
npm run dev -- -p 3002 &
FRONTEND_PID=$!

cleanup() {
  kill "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "✅ FORGE is running:"
echo "   Frontend: http://localhost:3002"
echo "   Backend:  http://localhost:5390"
echo ""
echo "Press Ctrl+C to stop both"

# Wait for either to exit
wait
