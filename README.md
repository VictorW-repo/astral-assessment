# Astral Technical Assessment - Victor Wang

**wars are won with logistics and propaganda**

A FastAPI application that builds an MVP for intelligent lead data collection and analysis, demonstrating async processing, web scraping, and thoughtful system design.

##  Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd astral-assessment

# Install dependencies
pip install -e .

# Copy environment variables
cp .env.example .env

# Start the server
./scripts/run.sh

# In another terminal, seed test data (3 scenarios)
./scripts/seed_examples.sh
```

Visit http://localhost:8000/docs for interactive API documentation.

##  Project Overview

This project implements a lead intelligence pipeline that:
1. Accepts registration data via REST API
2. Triggers asynchronous processing using Inngest
3. Discovers and analyzes company websites using Firecrawl
4. Outputs comprehensive JSON reports for each lead

### Core Philosophy

As an AI company operating at the cutting edge, we solve problems intelligently rather than with brute force. This project demonstrates:
- **Graceful degradation**: Works without API keys using fallback strategies
- **Intelligent filtering**: AI-driven URL relevance scoring
- **Async architecture**: Non-blocking request handling with queue-based processing
- **Pragmatic engineering**: Ship working code fast, optimize later

##  Architecture

```
/register endpoint → Inngest Event → Async Workflow → JSON Output
                          ↓
                  URL Discovery (Firecrawl)
                          ↓
                  Intelligent Filtering
                          ↓
                  Content Scraping (Markdown)
                          ↓
                  Structured JSON Report
```

##  Test Cases

The application includes three required test scenarios:

### 1. Website Only
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Alice","last_name":"Anderson","company_website":"https://stripe.com"}'
```

### 2. LinkedIn Only
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Bob","last_name":"Builder","linkedin":"https://linkedin.com/in/satyanadella"}'
```

### 3. Both Website and LinkedIn
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Charlie","last_name":"Chen","company_website":"https://openai.com","linkedin":"https://linkedin.com/in/gdb"}'
```

Run all three scenarios at once:
```bash
./scripts/seed_examples.sh
```

##  Output Format

Results are saved to `outputs/analysis_YYYYMMDD_HHMMSS_<request_id>.json`:

```json
{
  "request_id": "unique-identifier",
  "timestamp": "2025-08-31T14:30:22Z",
  "input_data": {
    "first_name": "...",
    "last_name": "...",
    "company_website": "...",
    "linkedin": "..."
  },
  "linkedin_analysis": {
    "status": "not_implemented"
  },
  "website_analysis": {
    "discovered_urls": ["list of all URLs found"],
    "filtered_urls": ["URLs selected for scraping"],
    "scraped_content": [
      {
        "url": "...",
        "content": "markdown content"
      }
    ],
    "statistics": {
      "total_discovered": 20,
      "total_filtered": 7,
      "total_scraped": 5
    }
  }
}
```

## 🔧 Setup Instructions

### Prerequisites

- Python 3.9+
- pip
- Optional: Inngest CLI for local development

### Installation

1. **Create virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -e .
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env to add API keys (optional - works without them)
```

4. **Run tests**:
```bash
pytest tests/ -v
```

### API Keys (Optional)

The application works without API keys using intelligent fallbacks:

- **Firecrawl**: Without key, uses common URL patterns
- **Inngest**: Without key, works in local development mode

To use full features, add keys to `.env`:
```env
FIRECRAWL_API_KEY=your_key_here
INNGEST_EVENT_KEY=your_key_here
```

##  LinkedIn Implementation Plan

While LinkedIn scraping is not implemented (as requested), here's the approach I would take:

### Recommended Solution: Proxycurl API

**Service**: [Proxycurl](https://nubela.co/proxycurl/)

**Why Proxycurl?**
- Legal and compliant LinkedIn data access
- Structured data output
- No authentication complexity
- Pay-per-use pricing

**Implementation Steps**:

1. **Add Configuration**:
```python
# core/config.py
PROXYCURL_API_KEY: str = Field(default=None)
PROXYCURL_API_URL: str = Field(default="https://api.proxycurl.com/v2")
```

2. **Create Client**:
```python
# core/clients/linkedin_client.py
class ProxycurlClient:
    async def get_profile(self, linkedin_url: str) -> Dict:
        # Extract username from URL
        # Call /api/v2/linkedin endpoint
        # Return structured data
```

3. **Extract Key Information**:
- Current position and company
- Work history
- Education
- Skills and endorsements
- Recent activity/posts
- Contact information (if available)

4. **Integration Points**:
```python
# features/workflows/register_workflow.py
if input_data.get("linkedin"):
    linkedin_result = await analyze_linkedin_proxycurl(
        input_data["linkedin"]
    )
```

### Alternative Solutions

1. **RapidAPI LinkedIn Endpoints**
   - Multiple providers available
   - Varies in data quality and pricing

2. **Bright Data's LinkedIn Dataset**
   - Pre-scraped data
   - More expensive but comprehensive

3. **ScraperAPI with Custom Logic**
   - More complex implementation
   - Requires handling anti-scraping measures

### Key Considerations

- **Legal Compliance**: Always use authorized APIs
- **Rate Limiting**: Implement exponential backoff
- **Data Privacy**: Only collect necessary information
- **Cost Optimization**: Cache results when possible

##  Key Design Decisions

### Why Inngest?

Inngest provides serverless queue management without complex infrastructure:
- Automatic retries with exponential backoff
- Step functions for workflow checkpointing
- Local development mode without external dependencies
- Simple integration with FastAPI

The challenge was discovering how to trigger Inngest functions from API endpoints - the solution involves creating a webhook endpoint that Inngest polls for function discovery.

### Why Firecrawl?

Firecrawl offers intelligent web scraping with:
- JavaScript rendering support
- Automatic sitemap discovery
- Rate limit handling
- Multiple output formats (we use Markdown for LLM compatibility)

### Why No Database?

Following the "less is more" principle:
- JSON files are sufficient for MVP
- No schema migrations needed
- Easy to inspect and debug
- Portable and version-controllable

##  Intelligent URL Filtering

The filtering algorithm scores URLs based on business intelligence value:

**High Value (+10 points)**:
- `/about`, `/team`, `/leadership`
- `/services`, `/solutions`
- `/case-studies`, `/portfolio`

**Low Value (-10 points)**:
- `/privacy`, `/terms`, `/cookie-policy`
- `/login`, `/signup`
- Image and asset files

**Result**: Top 7 URLs selected for scraping

##  Testing

Run the complete test suite:
```bash
pytest tests/ -v
```

Individual test files:
- `test_health.py` - Health endpoint validation
- `test_register_validation.py` - Input validation rules
- `test_output_shape.py` - JSON output structure

### Individual API Testing

Test each of the three supported scenarios individually:

**1. Website URL only:**
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Alice","last_name":"Anderson","company_website":"https://stripe.com"}'
```

**2. LinkedIn URL only:**
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Bob","last_name":"Builder","linkedin":"https://linkedin.com/in/satyanadella"}'
```

**3. Both provided:**
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Charlie","last_name":"Chen","company_website":"https://openai.com","linkedin":"https://linkedin.com/in/gdb"}'
```

## 📝 Development Notes

### Project Structure
```
astral-assessment/
├── api/                 # FastAPI routers and schemas
├── core/               # Configuration and utilities
├── features/           # Business logic
│   ├── workflows/      # Inngest async workflows
│   └── website_analysis/  # Scraping pipeline
├── tests/              # Comprehensive test suite
├── outputs/            # JSON output files
└── scripts/            # Developer tools
```

### Code Philosophy

Following Astral's engineering principles:
- **Fail gracefully**: Always return something useful
- **Question requirements**: Even (especially) from authority
- **Ship fast**: Working code > perfect code
- **Trust intuition**: Your compass in ambiguous situations

### Time Spent

This project was completed in approximately 6 hours:
- Architecture design: 1 hour
- Core implementation: 2 hours
- Inngest integration: 1 hours
- Testing and debugging: 1 hours
- Documentation: 1 hour

##  Production Considerations

For production deployment:

1. **Add monitoring**: Datadog/Sentry integration
2. **Implement caching**: Redis for URL discoveries
3. **Add authentication**: API key or OAuth
4. **Scale horizontally**: Multiple workers with load balancer
5. **Persistent storage**: PostgreSQL with SQLAlchemy
6. **Enhanced security**: Rate limiting, input sanitization

---

*"Wars are won with logistics and propaganda" - This project demonstrates both: the logistics of building scalable AI-enhanced systems and the propaganda of making them accessible and valuable to users.*