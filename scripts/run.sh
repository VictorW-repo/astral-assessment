#!/bin/bash

# Astral Assessment - Run Script
# Starts the FastAPI server with hot reload for development

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BLUE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   🚀 ASTRAL ASSESSMENT - FastAPI Server"
echo "   wars are won with logistics and propaganda"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo -e "${RED}❌ Error: main.py not found. Please run this script from the project root.${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found. Creating from .env.example...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Created .env file from .env.example${NC}"
        echo -e "${YELLOW}📝 Please edit .env to add your API keys if needed${NC}"
    else
        echo -e "${YELLOW}⚠️  No .env.example found. Using default settings.${NC}"
    fi
fi

# Create outputs directory if it doesn't exist
if [ ! -d "outputs" ]; then
    echo -e "${YELLOW}📁 Creating outputs directory...${NC}"
    mkdir -p outputs
    echo -e "${GREEN}✅ Created outputs directory${NC}"
fi

# Check if virtual environment exists
if [ -d "venv" ] || [ -d ".venv" ]; then
    echo -e "${GREEN}✅ Virtual environment detected${NC}"
    
    # Try to activate it
    if [ -f "venv/bin/activate" ]; then
        echo -e "${BLUE}🔧 Activating virtual environment (venv)...${NC}"
        source venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        echo -e "${BLUE}🔧 Activating virtual environment (.venv)...${NC}"
        source .venv/bin/activate
    fi
else
    echo -e "${YELLOW}⚠️  No virtual environment found. It's recommended to use one.${NC}"
    echo -e "${YELLOW}   Create one with: python -m venv venv${NC}"
fi

# Check if dependencies are installed
echo -e "${BLUE}🔍 Checking dependencies...${NC}"
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${RED}❌ FastAPI not installed!${NC}"
    echo -e "${YELLOW}📦 Installing dependencies from pyproject.toml...${NC}"
    
    if [ -f "pyproject.toml" ]; then
        pip install -e .
    else
        echo -e "${RED}❌ pyproject.toml not found!${NC}"
        echo -e "${YELLOW}Installing basic requirements...${NC}"
        pip install fastapi uvicorn httpx pydantic inngest
    fi
fi

# Check for Inngest Dev Server (optional but recommended)
echo -e "${BLUE}🔍 Checking for Inngest Dev Server...${NC}"
if command -v inngest-cli &> /dev/null; then
    echo -e "${GREEN}✅ Inngest CLI found${NC}"
    echo -e "${YELLOW}💡 Tip: Run 'inngest-cli dev' in another terminal for local Inngest testing${NC}"
else
    echo -e "${YELLOW}ℹ️  Inngest CLI not found (optional)${NC}"
    echo -e "${YELLOW}   Install with: curl -sfL https://inngest.com/cli.sh | sh${NC}"
fi

# Display environment info
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Environment Configuration:${NC}"
echo -e "  • Python: $(python --version 2>&1)"
echo -e "  • Working Directory: $(pwd)"
echo -e "  • Output Directory: ./outputs"

# Check API keys
if [ -f ".env" ]; then
    if grep -q "FIRECRAWL_API_KEY=" .env && ! grep -q "FIRECRAWL_API_KEY=$" .env; then
        echo -e "  • Firecrawl: ${GREEN}API key configured${NC}"
    else
        echo -e "  • Firecrawl: ${YELLOW}No API key (will use fallback)${NC}"
    fi
    
    if grep -q "INNGEST_EVENT_KEY=" .env && ! grep -q "INNGEST_EVENT_KEY=$" .env; then
        echo -e "  • Inngest: ${GREEN}Event key configured${NC}"
    else
        echo -e "  • Inngest: ${YELLOW}No event key (local mode)${NC}"
    fi
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Start the server
echo -e "${GREEN}🚀 Starting FastAPI server...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}📍 API Endpoints:${NC}"
echo -e "  • API:       ${BLUE}http://localhost:8000${NC}"
echo -e "  • Docs:      ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  • Health:    ${BLUE}http://localhost:8000/health${NC}"
echo -e "  • Register:  ${BLUE}http://localhost:8000/register${NC}"
echo -e "  • Inngest:   ${BLUE}http://localhost:8000/api/inngest${NC}"
echo ""
echo -e "${YELLOW}💡 Press CTRL+C to stop the server${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Run uvicorn with auto-reload
exec uvicorn main:app \
    --reload \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --reload-dir . \
    --reload-include "*.py" \
    --reload-include "*.json" \
    --reload-include ".env"