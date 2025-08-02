#!/bin/bash

# AI Response Bot Setup Script
# This script helps you set up the bot environment

set -e

echo "🤖 AI Response Bot Setup"
echo "========================"

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
required_version="3.8.0"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✅ Python $python_version is compatible"
else
    echo "❌ Python $python_version is too old. Requires Python 3.8+"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages

# Verify Ollama Python library
echo "🔍 Verifying Ollama Python library..."
python3 -c "import ollama; print('✅ Ollama Python library installed')" 2>/dev/null || {
    echo "📦 Installing Ollama Python library..."
    pip install ollama --break-system-packages
}

# Check if Ollama is installed
echo "🔍 Checking Ollama installation..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        echo "✅ Ollama is running"
    else
        echo "⚠️ Ollama is not running. Starting Ollama..."
        ollama serve &
        sleep 5
    fi
    
    # Check for models
    echo "🧠 Checking available models..."
    models=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | grep -v "^$")
    
    if [ -z "$models" ]; then
        echo "📥 No models found. Installing llama2..."
        ollama pull llama2
    else
        echo "✅ Available models:"
        echo "$models" | sed 's/^/  - /'
    fi
    
else
    echo "❌ Ollama not found. Please install Ollama:"
    echo "   curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi

# Setup configuration files
echo "⚙️ Setting up configuration..."

if [ ! -f "config.yaml" ]; then
    echo "📝 Creating config.yaml from example..."
    cp config.example.yaml config.yaml
    echo "✅ Created config.yaml - please customize it"
else
    echo "✅ config.yaml already exists"
fi

if [ ! -f ".env" ]; then
    echo "📝 Creating .env from example..."
    cp .env.example .env
    echo "⚠️ Please edit .env with your actual credentials"
else
    echo "✅ .env already exists"
fi

# Make CLI executable
echo "🔧 Setting up CLI..."
chmod +x cli.py

# Test the setup
echo "🧪 Testing setup..."
python3 cli.py test

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your Twitter API credentials"
echo "2. Customize config.yaml as needed"
echo "3. Run: python3 cli.py test"
echo "4. Run: python3 cli.py run-once"
echo "5. Run: python3 cli.py start"
echo ""
echo "For help: python3 cli.py --help"
