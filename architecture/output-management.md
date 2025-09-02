# Output Management Architecture

## Current Implementation

### File Naming Convention
- **Format**: `analysis_YYYYMMDD_HHMMSS_<request_id_suffix>.json`
- **Example**: `analysis_20250902_004016_4012d3a7.json`
- **Location**: `outputs/` directory

### Metadata
- **Fields**: filename, saved_at, version, philosophy
- **Processing Info**: Basic statistics (discovered, filtered, scraped counts)

## Enhancement Design Decisions

### 1. Human-Readable File Names
**Decision**: Include person names in output filenames for easier identification
**Rationale**: Improve file browsability and debugging experience
**Implementation**:
- **New Format**: `analysis_YYYYMMDD_HHMMSS_FirstLast_<short_id>.json`
- **Example**: `analysis_20250902_004016_CharlieC_4012d3a7.json`
- **Sanitization**: Remove special characters, limit length, handle unicode

### 2. Enhanced Metadata
**Decision**: Add comprehensive processing metadata for debugging and analytics
**Rationale**: Better observability into processing performance and issues
**Implementation**:
- Processing timestamps (start, end, duration)
- Resource usage statistics
- API call counts and response times
- Error summaries and retry counts
- Configuration snapshot

### 3. File Lifecycle Management
**Decision**: Add optional cleanup mechanism for old output files
**Rationale**: Prevent disk space issues in long-running environments
**Implementation**:
- Configurable retention period (default: no cleanup)
- Cleanup on startup if enabled
- Preserve files with errors for debugging

### 4. Structured Processing Logs
**Decision**: Embed detailed processing log in output for debugging
**Rationale**: Single file contains all information needed for troubleshooting
**Implementation**:
- Processing step timeline with timestamps
- API response summaries (without full content)
- Error details and recovery actions
- Performance metrics per phase

## Files Modified
- `core/utils.py` - Enhanced filename generation and metadata
- `features/workflows/register_workflow.py` - Add detailed logging
- `core/config.py` - Add output management configuration
- `.env.example` - Document new settings

## New Metadata Structure
```json
{
  "_metadata": {
    "filename": "analysis_20250902_004016_CharlieC_4012d3a7.json",
    "person_name": "Charlie Chen",
    "processing": {
      "started_at": "2025-09-02T04:40:12.282931+00:00",
      "completed_at": "2025-09-02T04:40:16.231492+00:00",
      "duration_seconds": 3.95,
      "steps": [
        {"step": "linkedin_analysis", "duration_ms": 5, "status": "skipped"},
        {"step": "url_discovery", "duration_ms": 1200, "status": "success", "api_calls": 1},
        {"step": "url_filtering", "duration_ms": 10, "status": "success"},
        {"step": "content_scraping", "duration_ms": 2800, "status": "success", "api_calls": 1}
      ]
    },
    "resources": {
      "api_calls_total": 2,
      "content_bytes_scraped": 7645,
      "urls_processed": 1
    },
    "version": "1.1.0",
    "philosophy": "wars are won with logistics and propaganda"
  }
}
```

## Configuration Options
```env
OUTPUT_INCLUDE_PERSON_NAME=true
OUTPUT_RETENTION_DAYS=30
OUTPUT_CLEANUP_ON_STARTUP=false
OUTPUT_DETAILED_LOGGING=true
```

## Backwards Compatibility
- Enhanced metadata is additive - all existing fields preserved
- New filename format only used when person name available
- Legacy format still supported for edge cases