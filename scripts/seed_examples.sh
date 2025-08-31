#!/bin/bash

# Astral Assessment - Seed Examples Script
# Seeds the API with the three required test scenarios

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default API URL
API_URL="${API_URL:-http://localhost:8000}"

# Print banner
echo -e "${BLUE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   🌱 ASTRAL ASSESSMENT - Seed Test Examples"
echo "   Testing 3 required scenarios"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"

# Function to check if server is running
check_server() {
    echo -e "${BLUE}🔍 Checking if server is running at ${API_URL}...${NC}"
    
    if curl -s -f -o /dev/null "${API_URL}/health"; then
        echo -e "${GREEN}✅ Server is running!${NC}"
        return 0
    else
        echo -e "${RED}❌ Server is not running at ${API_URL}${NC}"
        echo -e "${YELLOW}Please start the server first with: ./scripts/run.sh${NC}"
        return 1
    fi
}

# Function to make a registration request
register() {
    local first_name=$1
    local last_name=$2
    local company_website=$3
    local linkedin=$4
    local scenario=$5
    
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Scenario: ${scenario}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Build JSON payload
    local json_payload="{\"first_name\":\"${first_name}\",\"last_name\":\"${last_name}\""
    
    if [ -n "$company_website" ] && [ "$company_website" != "null" ]; then
        json_payload="${json_payload},\"company_website\":\"${company_website}\""
    fi
    
    if [ -n "$linkedin" ] && [ "$linkedin" != "null" ]; then
        json_payload="${json_payload},\"linkedin\":\"${linkedin}\""
    fi
    
    json_payload="${json_payload}}"
    
    echo -e "${BLUE}📤 Request:${NC}"
    echo "$json_payload" | python -m json.tool 2>/dev/null || echo "$json_payload"
    echo ""
    
    # Make the request
    response=$(curl -s -X POST "${API_URL}/register" \
        -H "Content-Type: application/json" \
        -d "$json_payload")
    
    # Check if request was successful
    if echo "$response" | grep -q "accepted"; then
        echo -e "${GREEN}✅ Success!${NC}"
        echo -e "${BLUE}📥 Response:${NC}"
        echo "$response" | python -m json.tool 2>/dev/null || echo "$response"
        
        # Extract request_id
        request_id=$(echo "$response" | grep -o '"request_id":"[^"]*"' | cut -d'"' -f4)
        if [ -n "$request_id" ]; then
            echo -e "${GREEN}📝 Request ID: ${request_id}${NC}"
        fi
    else
        echo -e "${RED}❌ Failed!${NC}"
        echo -e "${RED}Response:${NC}"
        echo "$response" | python -m json.tool 2>/dev/null || echo "$response"
    fi
    
    echo ""
}

# Function to test validation errors
test_validation() {
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Bonus: Testing validation error (should fail)${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    local json_payload='{"first_name":"Invalid","last_name":"Test"}'
    
    echo -e "${BLUE}📤 Request (missing both URLs):${NC}"
    echo "$json_payload" | python -m json.tool
    echo ""
    
    response=$(curl -s -X POST "${API_URL}/register" \
        -H "Content-Type: application/json" \
        -d "$json_payload")
    
    if echo "$response" | grep -q "detail"; then
        echo -e "${GREEN}✅ Validation correctly rejected the request${NC}"
        echo -e "${BLUE}📥 Error Response:${NC}"
        echo "$response" | python -m json.tool 2>/dev/null || echo "$response"
    else
        echo -e "${RED}❌ Validation should have failed but didn't${NC}"
        echo "$response"
    fi
    
    echo ""
}

# Main execution
main() {
    # Check if server is running
    if ! check_server; then
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}🚀 Starting test scenarios...${NC}"
    echo ""
    
    # Wait a moment for server to be fully ready
    sleep 1
    
    # Scenario 1: Website Only
    register \
        "Alice" \
        "Anderson" \
        "https://stripe.com" \
        "null" \
        "Website Only"
    
    sleep 1  # Small delay between requests
    
    # Scenario 2: LinkedIn Only
    register \
        "Bob" \
        "Builder" \
        "null" \
        "https://linkedin.com/in/satyanadella" \
        "LinkedIn Only"
    
    sleep 1
    
    # Scenario 3: Both Website and LinkedIn
    register \
        "Charlie" \
        "Chen" \
        "https://openai.com" \
        "https://linkedin.com/in/gdb" \
        "Both Website and LinkedIn"
    
    sleep 1
    
    # Bonus: Test validation error
    test_validation
    
    # Summary
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✨ All test scenarios completed!${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}📁 Check the outputs/ directory for generated JSON files${NC}"
    echo -e "${YELLOW}📊 View API docs at: ${API_URL}/docs${NC}"
    echo -e "${YELLOW}🔍 Check health status at: ${API_URL}/health/detailed${NC}"
    echo ""
    
    # List recent output files if any exist
    if [ -d "outputs" ] && [ "$(ls -A outputs/*.json 2>/dev/null)" ]; then
        echo -e "${GREEN}📄 Recent output files:${NC}"
        ls -lt outputs/*.json 2>/dev/null | head -5 | awk '{print "   • " $9}'
    fi
    
    echo ""
    echo -e "${CYAN}wars are won with logistics and propaganda${NC}"
}

# Handle script arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --url)
            API_URL="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--url API_URL]"
            echo ""
            echo "Options:"
            echo "  --url API_URL    Set the API URL (default: http://localhost:8000)"
            echo "  --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Use default localhost:8000"
            echo "  $0 --url http://localhost:3000  # Use custom port"
            echo "  $0 --url https://api.example.com # Use remote API"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main