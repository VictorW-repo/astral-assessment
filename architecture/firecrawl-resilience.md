# Firecrawl Resilience Architecture

## Current Implementation

### Rate Limit Handling
- **Method**: Simple status code check (429)
- **Response**: Return rate_limited status and fallback to base URL
- **Concurrency**: Basic semaphore limiting (max 3 concurrent)

### Error Recovery
- **Timeouts**: Fixed timeout with exception handling
- **Retries**: No automatic retries implemented
- **Fallback**: Mock responses when API key missing

## Enhancement Design Decisions

### 1. Exponential Backoff Strategy
**Decision**: Implement exponential backoff for rate-limited requests
**Rationale**: Respect API rate limits while maximizing successful requests
**Implementation**:
- Start with 1 second delay, double each retry up to 60 seconds
- Maximum 3 retry attempts for rate limits
- Jitter randomization to prevent thundering herd

### 2. Request Queuing
**Decision**: Add intelligent request queuing to prevent rate limit hits
**Rationale**: Proactive rate limit management vs reactive handling
**Implementation**:
- Track request timestamps and enforce minimum intervals
- Queue requests when approaching rate limits
- Configurable requests per minute limit

### 3. Enhanced Error Classification
**Decision**: Categorize errors by retry-ability and appropriate responses
**Rationale**: Different error types need different handling strategies
**Implementation**:
- Transient errors (timeouts, 5xx): Retry with backoff
- Client errors (4xx): No retry, return error immediately  
- Rate limits (429): Backoff and retry
- Network errors: Retry with exponential backoff

### 4. Circuit Breaker Pattern
**Decision**: Implement circuit breaker for Firecrawl API calls
**Rationale**: Prevent cascading failures when API is consistently failing
**Implementation**:
- Track failure rate over sliding window
- Open circuit after threshold failures (e.g., 5 in 60 seconds)
- Half-open state for gradual recovery testing

## Files Modified
- `core/clients/firecrawl.py` - Enhanced with backoff and queuing
- `core/config.py` - Add resilience configuration options
- `.env.example` - Document new configuration variables

## Configuration Options
```env
FIRECRAWL_MAX_RETRIES=3
FIRECRAWL_BASE_DELAY_SECONDS=1
FIRECRAWL_MAX_DELAY_SECONDS=60
FIRECRAWL_REQUESTS_PER_MINUTE=30
FIRECRAWL_CIRCUIT_BREAKER_FAILURES=5
FIRECRAWL_CIRCUIT_BREAKER_WINDOW_SECONDS=60
```

## Backwards Compatibility
- All resilience features are opt-in via configuration
- Default behavior unchanged when new settings not provided
- Existing error handling preserved and enhanced