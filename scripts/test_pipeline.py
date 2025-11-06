#!/usr/bin/env python3
"""
Comprehensive Pipeline Test Script for Elara AI v2.0

Tests all major components:
1. Fashion trends fetcher
2. Wardrobe gap analyzer
3. Hybrid product search (Vector DB + Google Shopping + ASOS + Scrapers)
4. Multi-signal ranking engine
5. LLM reasoning with dynamic trends
6. End-to-end outfit generation

Usage:
    python scripts/test_pipeline.py --all           # Test everything
    python scripts/test_pipeline.py --trends        # Test fashion trends
    python scripts/test_pipeline.py --search        # Test product search
    python scripts/test_pipeline.py --gaps          # Test wardrobe gaps
    python scripts/test_pipeline.py --e2e           # Test end-to-end
"""
import sys
import json
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.fashion_trends_fetcher import get_current_trends, score_product_for_trends
from services.wardrobe_analyzer import analyze_for_occasion, analyze_versatility
from services.product_search_service import search_products_hybrid
from llm_reasoning import generate_outfits
import config


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_fashion_trends():
    """Test the fashion trends fetcher."""
    print_section("TEST 1: Fashion Trends Fetcher")

    print("🔍 Fetching current fashion trends...")
    trends = get_current_trends()

    print(f"\n📅 Last Updated: {trends.get('last_updated')}")
    print(f"📚 Sources: {', '.join(trends.get('sources', [])[:2])}")

    print("\n🎨 Current Style Movements:")
    for i, movement in enumerate(trends.get('style_movements', [])[:3], 1):
        print(f"\n{i}. {movement.get('name')}")
        print(f"   {movement.get('description')[:100]}...")
        print(f"   Keywords: {', '.join(movement.get('keywords', [])[:5])}")
        print(f"   Confidence: {movement.get('confidence'):.0%}")

    print("\n🌈 Seasonal Color Palette:")
    seasonal = trends.get('color_trends', {}).get('seasonal_palette', {})
    print(f"   {seasonal.get('season')}: {', '.join(seasonal.get('colors', [])[:5])}")

    # Test trend scoring
    print("\n📊 Testing Trend Scoring:")
    test_products = [
        ("Oversized Cashmere Sweater in Cream", "Quiet luxury piece"),
        ("Fast Fashion Polyester Dress", "Trendy party dress"),
        ("Sustainable Organic Cotton Wide-Leg Pants", "Eco-friendly bottoms"),
    ]

    for title, desc in test_products:
        score = score_product_for_trends(title, desc)
        print(f"   '{title}': {score:.2f}/1.0")

    print("\n✅ Fashion Trends Test Complete!")


def test_wardrobe_gaps():
    """Test the wardrobe gap analyzer."""
    print_section("TEST 2: Wardrobe Gap Analyzer")

    # Sample wardrobe
    test_wardrobe = [
        {"id": "1", "category": "tops", "name": "White button-down shirt"},
        {"id": "2", "category": "tops", "name": "Black t-shirt"},
        {"id": "3", "category": "bottoms", "name": "Dark blue jeans"},
        {"id": "4", "category": "footwear", "name": "White sneakers"},
    ]

    print("👔 Sample Wardrobe:")
    for item in test_wardrobe:
        print(f"   - {item['name']} ({item['category']})")

    # Test different occasions
    occasions = ["office_professional", "date_night", "casual_everyday"]

    for occasion in occasions:
        print(f"\n🎯 Analyzing for: {occasion.replace('_', ' ').title()}")
        analysis = analyze_for_occasion(test_wardrobe, occasion)

        print(f"   ✓ Has sufficient items: {analysis['has_sufficient_items']}")

        if analysis['missing_essentials']:
            print(f"   ⚠️  Missing essentials: {', '.join(analysis['missing_essentials'][:3])}")

        if analysis['high_impact_purchases']:
            print(f"   💡 High-impact purchases: {', '.join(analysis['high_impact_purchases'][:2])}")

        print(f"   💬 Gap reasoning: {analysis['gap_reasoning'][:80]}...")

    # Test versatility analysis
    print("\n🔄 Testing Wardrobe Versatility Analysis:")
    versatility = analyze_versatility(test_wardrobe)
    print(f"   Overall versatility score: {versatility['versatility_score']:.1f}/100")

    if versatility['top_recommendations']:
        print(f"   Top 3 recommendations:")
        for rec in versatility['top_recommendations'][:3]:
            print(f"   - {rec['item'].replace('_', ' ').title()} (unlocks {rec['impact']} occasions)")

    print("\n✅ Wardrobe Gap Analysis Test Complete!")


async def test_product_search():
    """Test the hybrid product search."""
    print_section("TEST 3: Hybrid Product Search")

    test_queries = [
        {
            "descriptor": "black leather Chelsea boots men's",
            "budget": {"soft_cap": 150, "hard_cap": 300},
            "filters": {"gender": "men", "color": "black"},
        },
        {
            "descriptor": "sustainable organic cotton white t-shirt women's",
            "budget": {"soft_cap": 50, "hard_cap": 100},
            "filters": {"gender": "women"},
        },
        {
            "descriptor": "navy blue blazer men's slim fit",
            "budget": {"soft_cap": 200, "hard_cap": 400},
            "filters": {"gender": "men", "color": "navy"},
        },
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n🔍 Query {i}: {query['descriptor']}")
        print(f"   Budget: ${query['budget']['soft_cap']}-${query['budget']['hard_cap']}")

        try:
            products = await search_products_hybrid(
                descriptor=query['descriptor'],
                budget=query['budget'],
                filters=query['filters'],
                k=10
            )

            print(f"\n   ✅ Found {len(products)} products from multiple sources:")

            # Group by source
            by_source = {}
            for p in products:
                by_source.setdefault(p.source, []).append(p)

            for source, prods in by_source.items():
                print(f"      - {source}: {len(prods)} products")

            # Show top 3 results
            print(f"\n   📦 Top 3 Results:")
            for j, product in enumerate(products[:3], 1):
                print(f"      {j}. {product.title[:60]}")
                print(f"         ${product.price} at {product.retailer} (source: {product.source})")
                print(f"         Relevance: {product.relevance_score:.2f}")

        except Exception as e:
            print(f"   ❌ Search failed: {e}")

        print()

    print("✅ Product Search Test Complete!")


async def test_end_to_end():
    """Test end-to-end outfit generation."""
    print_section("TEST 4: End-to-End Outfit Generation")

    # Sample context pack
    context_pack = {
        "session": {
            "location": "New York, NY",
            "datetime_local_iso": "2025-01-20T18:00:00",
            "occasion": "Business Casual Office",
            "vibe": "Professional but comfortable"
        },
        "user_profile": {
            "gender": "Men",
            "skin_tone": "Fair",
            "brand_prefs": ["Zara", "H&M", "ASOS"],
            "color_prefs": ["Navy", "Gray", "White"],
            "body_type": "Athletic",
            "fit_pref": "Slim",
            "style_pref": "Modern Minimalist",
            "budget": {
                "currency": "USD",
                "soft_cap": 150,
                "hard_cap": 300
            }
        },
        "weather_compact": {
            "temp_c": 5,
            "condition": "Cold and clear"
        },
        "constraints": {
            "max_online_items_per_look": 3,
            "retailers_allowlist": ["Zara", "H&M", "ASOS", "Nordstrom"]
        },
        "wardrobe": [
            {
                "id": "w1",
                "category": "Tops",
                "name": "White Oxford Shirt",
                "color": "White",
                "brand": "Uniqlo"
            },
            {
                "id": "w2",
                "category": "Bottoms",
                "name": "Dark Navy Chinos",
                "color": "Navy",
                "brand": "Gap"
            },
            {
                "id": "w3",
                "category": "Footwear",
                "name": "Brown Leather Loafers",
                "color": "Brown",
                "brand": "Cole Haan"
            }
        ],
        "wardrobe_index": {
            "Tops": ["w1"],
            "Bottoms": ["w2"],
            "Footwear": ["w3"]
        },
        "trend_tags": ["professional", "minimalist", "quality"]
    }

    print("🎯 Testing Full Pipeline with Sample Context:")
    print(f"   Location: {context_pack['session']['location']}")
    print(f"   Occasion: {context_pack['session']['occasion']}")
    print(f"   Budget: ${context_pack['user_profile']['budget']['soft_cap']}-${context_pack['user_profile']['budget']['hard_cap']}")
    print(f"   Wardrobe Size: {len(context_pack['wardrobe'])} items")

    print("\n⚙️  Running LLM Reasoning Layer...")

    try:
        result = generate_outfits(context_pack)

        print(f"\n✅ Generated {len(result.get('outfits', []))} Outfit Recommendations!\n")

        for i, outfit in enumerate(result.get('outfits', []), 1):
            print(f"{'─' * 80}")
            print(f"OUTFIT {i}: {outfit.get('name', 'Unnamed')}")
            print(f"{'─' * 80}")
            print(f"Vibe: {outfit.get('vibe', 'N/A')}")
            print(f"Summary: {outfit.get('summary', 'N/A')}")

            composition = outfit.get('composition', [])
            print(f"\nPieces ({len(composition)} items):")

            wardrobe_count = 0
            shopping_count = 0

            for item in composition:
                source = item.get('source', 'unknown')
                slot = item.get('slot', 'item')
                descriptor = item.get('descriptor', 'N/A')

                if source == 'wardrobe':
                    wardrobe_count += 1
                    wardrobe_id = item.get('wardrobe_item_id', '?')
                    print(f"   ✓ {slot.upper()}: From wardrobe (ID: {wardrobe_id})")
                else:
                    shopping_count += 1
                    budget_tier = item.get('budget_tier', 'unknown')
                    gap_reason = item.get('gap_reason', '')
                    print(f"   🛒 {slot.upper()}: {descriptor}")
                    print(f"      Tier: {budget_tier} | Reason: {gap_reason[:50]}...")

            print(f"\n   Stats: {wardrobe_count} from wardrobe, {shopping_count} to purchase")

        # Show wardrobe analysis if present
        if 'wardrobe_analysis' in result:
            analysis = result['wardrobe_analysis']
            print(f"\n{'─' * 80}")
            print("WARDROBE GAP ANALYSIS")
            print(f"{'─' * 80}")
            print(f"Has sufficient items: {analysis.get('has_sufficient_items')}")
            print(f"Gap reasoning: {analysis.get('gap_reasoning', 'N/A')}")
            if analysis.get('high_impact_purchases'):
                print(f"High-impact purchases: {', '.join(analysis['high_impact_purchases'])}")

        print("\n✅ End-to-End Test Complete!")

    except Exception as e:
        print(f"\n❌ LLM Reasoning failed: {e}")
        import traceback
        traceback.print_exc()


def test_configuration():
    """Test configuration and API keys."""
    print_section("TEST 0: Configuration Check")

    print("🔧 Checking API Keys and Configuration...")

    checks = [
        ("OpenAI API Key", config.OPENAI_API_KEY, True),
        ("OpenAI Reasoning Model", config.OPENAI_REASONING_MODEL, True),
        ("OpenAI Mini Model", config.OPENAI_MINI_MODEL, True),
        ("Database DSN", config.PG_DSN, True),
        ("Redis URL", config.REDIS_URL, True),
        ("Google Shopping API Key", getattr(config, "GOOGLE_SHOPPING_API_KEY", ""), False),
        ("OpenWeather API Key", getattr(config, "OPENWEATHER_API_KEY", ""), False),
    ]

    all_required_ok = True

    for name, value, required in checks:
        # Check if value is valid (not empty, not a placeholder)
        is_valid = bool(value and
                       value != "your_key_here" and
                       value != "your_openweather_key_here" and
                       value != "your_google_api_key_here" and
                       not value.startswith("your_") and
                       "sk-proj-your_key_here" not in value)

        if is_valid:
            status = "✅"
            detail = "Configured"
        elif required:
            status = "❌"
            detail = "MISSING (Required)"
            all_required_ok = False
        else:
            status = "⚠️"
            detail = "Not configured (Optional)"

        print(f"   {status} {name}: {detail}")

    print()

    if not all_required_ok:
        print("❌ Missing required configuration! Please set up .env file.")
        print("   Copy .env.sample to .env and add your API keys.")
        return False
    else:
        print("✅ All required configuration is present!")
        return True


async def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Elara AI v2.0 Pipeline")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--config", action="store_true", help="Test configuration")
    parser.add_argument("--trends", action="store_true", help="Test fashion trends")
    parser.add_argument("--gaps", action="store_true", help="Test wardrobe gaps")
    parser.add_argument("--search", action="store_true", help="Test product search")
    parser.add_argument("--e2e", action="store_true", help="Test end-to-end")

    args = parser.parse_args()

    # If no args, show help
    if not any(vars(args).values()):
        parser.print_help()
        return

    print("\n" + "=" * 80)
    print("  🤖 ELARA AI v2.0 - PIPELINE TEST SUITE")
    print("=" * 80)

    # Always check config first
    config_ok = test_configuration()

    if not config_ok:
        print("\n⚠️  Configuration issues found. Some tests may fail.")
        print("    Continue anyway? [y/N]: ", end="")
        response = input().strip().lower()
        if response != 'y':
            return

    try:
        if args.all or args.trends:
            test_fashion_trends()

        if args.all or args.gaps:
            test_wardrobe_gaps()

        if args.all or args.search:
            await test_product_search()

        if args.all or args.e2e:
            await test_end_to_end()

        print("\n" + "=" * 80)
        print("  ✅ ALL TESTS COMPLETED!")
        print("=" * 80 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
