#!/usr/bin/env python3
"""
Debug script to test Firecrawl API key validation and example.com crawling.
"""

import asyncio
import sys
import logging

# Set up logging to see all details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add current directory to path
sys.path.insert(0, '.')

from core.clients import firecrawl

async def main():
    print("=== Firecrawl API Debug Test ===")
    
    # Test 1: Validate API key
    print("\n1. Testing API key validation...")
    try:
        validation_result = await firecrawl.validate_api_key()
        print(f"   Status: {validation_result['status']}")
        print(f"   Valid: {validation_result['valid']}")
        print(f"   Message: {validation_result['message']}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 2: Try scraping example.com 
    print("\n2. Testing example.com scraping...")
    try:
        scrape_result = await firecrawl.scrape("https://example.com")
        print(f"   Status: {scrape_result['status']}")
        if scrape_result['status'] == 'success':
            print(f"   Content length: {len(scrape_result.get('content', ''))}")
        else:
            print(f"   Reason: {scrape_result.get('reason', 'unknown')}")
            if 'human_readable_error' in scrape_result:
                print(f"   Error: {scrape_result['human_readable_error']}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 3: Try crawling example.com (minimal)
    print("\n3. Testing example.com crawling...")
    try:
        crawl_result = await firecrawl.crawl("https://example.com", limit=1)
        print(f"   Status: {crawl_result['status']}")
        print(f"   URLs found: {len(crawl_result.get('urls', []))}")
        if 'urls' in crawl_result and crawl_result['urls']:
            print(f"   URLs: {crawl_result['urls']}")
        if crawl_result.get('status') != 'success':
            print(f"   Reason: {crawl_result.get('reason', 'unknown')}")
            if 'human_readable_error' in crawl_result:
                print(f"   Error: {crawl_result['human_readable_error']}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 4: Test full workflow with example.com
    print("\n4. Testing full workflow with example.com...")
    try:
        sys.path.insert(0, '.')
        from features.workflows.register_workflow import execute_registration_workflow_sync
        
        test_data = {
            'request_id': 'test-example-com',
            'timestamp': '2025-09-02T20:50:00Z',
            'first_name': 'Example',
            'last_name': 'Test',
            'company_website': 'https://example.com',
            'linkedin': None
        }
        
        result = await execute_registration_workflow_sync(test_data)
        website_analysis = result.get('website_analysis', {})
        
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   URLs discovered: {len(website_analysis.get('discovered_urls', []))}")
        print(f"   URLs filtered: {len(website_analysis.get('filtered_urls', []))}")
        print(f"   Content scraped: {len(website_analysis.get('scraped_content', []))}")
        
        # Check if we got actual content
        scraped_content = website_analysis.get('scraped_content', [])
        if scraped_content:
            first_content = scraped_content[0]
            content_text = first_content.get('content', '')
            print(f"   Content length: {len(content_text)}")
            if content_text:
                preview = content_text[:100].replace('\n', ' ')
                print(f"   Content preview: {preview}...")
                print(f"   Scraping method: {first_content.get('method', 'unknown')}")
            
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 5: Test with a real business website (should show 402 handling)
    print("\n5. Testing with real business website (OpenAI)...")
    try:
        test_data_business = {
            'request_id': 'test-business-website',
            'timestamp': '2025-09-02T20:55:00Z',
            'first_name': 'Business',
            'last_name': 'Test',
            'company_website': 'https://openai.com',
            'linkedin': None
        }
        
        result = await execute_registration_workflow_sync(test_data_business)
        website_analysis = result.get('website_analysis', {})
        
        print(f"   URLs discovered: {len(website_analysis.get('discovered_urls', []))}")
        print(f"   URLs filtered: {len(website_analysis.get('filtered_urls', []))}")
        print(f"   Content scraped: {len(website_analysis.get('scraped_content', []))}")
        
        # Check error handling
        metadata = result.get('_metadata', {})
        if 'error_summary' in metadata:
            error_summary = metadata['error_summary']
            print(f"   Error detected: {error_summary.get('has_errors', False)}")
            print(f"   User message: {error_summary.get('user_message', 'N/A')}")
            print(f"   Recommended actions: {error_summary.get('recommended_actions', [])}")
        
        # Check if fallback was used  
        scraped_content = website_analysis.get('scraped_content', [])
        if scraped_content:
            first_content = scraped_content[0]
            if 'human_readable_error' in first_content:
                print(f"   Scraping error: {first_content['human_readable_error']}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print("\n=== Debug Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())