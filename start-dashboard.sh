#!/bin/bash

# AI Crucible - War Room Dashboard Startup Script

echo "🛡️  AI Crucible - War Room Dashboard"
echo "===================================="
echo ""

# Check if backend venv exists
if [ ! -d "backend/venv" ]; then
    echo "❌ Backend virtual environment not found!"
    echo "   Run: cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if frontend node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo "❌ Frontend dependencies not installed!"
    echo "   Run: cd frontend && npm install"
    exit 1
fi

echo "✅ Dependencies found"
echo ""

# Start backend in background
echo "🚀 Starting backend server..."
cd backend
source venv/bin/activate
python -m src.server &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 2

# Start frontend
echo "🚀 Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Servers started!"
echo ""
echo "📡 Backend:  http://localhost:8000"
echo "🎨 Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for user interrupt
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
