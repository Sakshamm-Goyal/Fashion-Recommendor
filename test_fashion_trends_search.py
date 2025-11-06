#!/usr/bin/env python3
"""
Test script for fashion trends web search functionality.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_duckduckgo_import():
    """Test if DuckDuckGo package can be imported."""
    print("=" * 60)
    print("TEST 1: DuckDuckGo Package Import")
    print("=" * 60)
    
    try:
        from duckduckgo_search import DDGS
        print("✅ SUCCESS: duckduckgo_search imported successfully")
        return True
    except ImportError as e:
        print(f"❌ FAILED: {e}")
        print("\n💡 SOLUTION: Install the package with:")
        print("   pip install duckduckgo-search")
        return False

def test_duckduckgo_search():
    """Test DuckDuckGo search functionality."""
    print("\n" + "=" * 60)
    print("TEST 2: DuckDuckGo Search Functionality")
    print("=" * 60)
    
    try:
        from duckduckgo_search import DDGS
        
        print("Testing search query: 'fashion trends 2025'")
        
        with DDGS() as ddgs:
            results = list(ddgs.text(
                keywords="fashion trends 2025",
                max_results=3,
                region='us-en',
                safesearch='moderate'
            ))
            
            print(f"✅ SUCCESS: Found {len(results)} results")
            
            if results:
                print("\nSample result structure:")
                first = results[0]
                print(f"  - Keys: {list(first.keys())}")
                print(f"  - Title: {first.get('title', 'N/A')[:80]}...")
                print(f"  - Has 'body' field: {'body' in first}")
                print(f"  - Has 'href' field: {'href' in first}")
                
                # Verify expected fields
                expected_fields = ['title', 'body', 'href']
                missing = [f for f in expected_fields if f not in first]
                if missing:
                    print(f"⚠️  WARNING: Missing fields: {missing}")
                else:
                    print("✅ All expected fields present")
            
            return True
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fashion_trends_fetcher():
    """Test the fashion trends fetcher implementation."""
    print("\n" + "=" * 60)
    print("TEST 3: Fashion Trends Fetcher (Web Search)")
    print("=" * 60)
    
    try:
        from services.fashion_trends_fetcher import FashionTrendsFetcher
        
        fetcher = FashionTrendsFetcher(cache_ttl_days=7)
        
        print("Testing web search method...")
        search_results = fetcher._perform_web_search("fashion trends 2025 Spring", max_results=3)
        
        if search_results:
            print(f"✅ SUCCESS: Got {len(search_results)} search results")
            print("\nSample result:")
            first = search_results[0]
            for key, value in first.items():
                print(f"  {key}: {str(value)[:100]}...")
            return True
        else:
            print("⚠️  WARNING: No search results returned (may need to install package)")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_full_flow():
    """Test the full flow with force refresh."""
    print("\n" + "=" * 60)
    print("TEST 4: Full Fashion Trends Flow (with web search)")
    print("=" * 60)
    
    try:
        from services.fashion_trends_fetcher import get_current_trends
        
        print("Fetching trends with force_refresh=True (will trigger web search)...")
        print("(This may take 10-30 seconds as it performs web search + OpenAI extraction)")
        
        trends = get_current_trends(force_refresh=True)
        
        if trends:
            print(f"✅ SUCCESS: Got trends data")
            print(f"  - Last updated: {trends.get('last_updated', 'N/A')}")
            print(f"  - Sources: {len(trends.get('sources', []))} sources")
            print(f"  - Style movements: {len(trends.get('style_movements', []))} trends")
            
            if trends.get('style_movements'):
                print("\n  Sample trend:")
                first_trend = trends['style_movements'][0]
                print(f"    - Name: {first_trend.get('name', 'N/A')}")
                print(f"    - Description: {first_trend.get('description', 'N/A')[:80]}...")
            
            return True
        else:
            print("❌ FAILED: No trends returned")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🧪 Testing Fashion Trends Web Search Implementation\n")
    
    results = []
    
    # Test 1: Import
    results.append(("Import", test_duckduckgo_import()))
    
    # Test 2: Basic search (only if import works)
    if results[0][1]:
        results.append(("Search", test_duckduckgo_search()))
        results.append(("Fetcher", test_fashion_trends_fetcher()))
        
        # Test 4: Full flow (optional - requires OpenAI API key)
        print("\n" + "=" * 60)
        print("TEST 4: Full Flow (requires OpenAI API key)")
        print("=" * 60)
        response = input("Run full flow test? This will use OpenAI API (costs ~$0.01) [y/N]: ")
        if response.lower() == 'y':
            results.append(("Full Flow", test_full_flow()))
        else:
            print("Skipped full flow test")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name:20s} {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + ("✅ ALL TESTS PASSED" if all_passed else "⚠️  SOME TESTS FAILED"))
    print("\n" + "=" * 60)

