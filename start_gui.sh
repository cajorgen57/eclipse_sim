#!/bin/bash
# Quick start script for Eclipse AI Testing GUI

echo "=================================================="
echo "Eclipse AI Testing GUI - Quick Start"
echo "=================================================="
echo ""

# Check if GUI dependencies are installed
echo "Checking dependencies..."
python -c "import fastapi, uvicorn, jinja2" 2>/dev/null

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  GUI dependencies not found."
    echo "Installing dependencies..."
    echo ""
    pip install "fastapi>=0.104.0" "uvicorn[standard]>=0.24.0" "python-multipart>=0.0.6" "jinja2>=3.1.0"
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Failed to install dependencies."
        echo "Please run manually: pip install -e \".[gui]\""
        exit 1
    fi
else
    echo "✓ Dependencies installed"
fi

echo ""
echo "Starting GUI server..."
echo ""
echo "=================================================="
echo "Open your browser to: http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo "=================================================="
echo ""

# Start the GUI
python -m eclipse_ai.gui.run

