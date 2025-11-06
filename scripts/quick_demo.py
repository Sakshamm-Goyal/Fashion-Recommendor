#!/usr/bin/env python3
"""
Quick Demo Script for Elara AI v2.0

A simple, interactive demo that showcases the core features:
- Fashion trend intelligence
- Wardrobe gap analysis
- Hybrid product search
- AI outfit recommendations

Usage:
    python scripts/quick_demo.py
"""
import sys
import json
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.fashion_trends_fetcher import get_current_trends
from services.wardrobe_analyzer import analyze_for_occasion
from services.product_search_service import search_products_hybrid


def print_header(text: str):
    """Print a fancy header."""
    print("\n" + "╔" + "═" * 78 + "╗")
    print(f"║  {text:<75} ║")
    print("╚" + "═" * 78 + "╝\n")


def print_step(step: int, text: str):
    """Print a step header."""
    print(f"\n{'─' * 80}")
    print(f"STEP {step}: {text}")
    print('─' * 80)


async def demo_fashion_trends():
    """Demo: Fashion Trends Intelligence."""
    print_header("🎨 FASHION TRENDS INTELLIGENCE")

    print("Elara stays up-to-date with current fashion trends from authoritative sources.")
    print("Trends are fetched dynamically and cached for 7 days.\n")

    trends = get_current_trends()

    print(f"📅 Last Updated: {trends.get('last_updated')}")
    print(f"📚 Sources: Vogue, Harper's Bazaar, Pinterest Predicts, Business of Fashion\n")

    print("🔥 Top 3 Current Trends:\n")
    for i, movement in enumerate(trends.get('style_movements', [])[:3], 1):
        print(f"{i}. {movement.get('name')}")
        print(f"   {movement.get('description')[:120]}...")
        print()


async def demo_wardrobe_gap():
    """Demo: Wardrobe Gap Analysis."""
    print_header("🔍 WARDROBE GAP ANALYSIS")

    print("Elara analyzes your wardrobe and identifies missing pieces for specific occasions.\n")

    # Sample minimal wardrobe
    sample_wardrobe = [
        {"id": "1", "category": "tops", "name": "White button-down shirt"},
        {"id": "2", "category": "tops", "name": "Black t-shirt"},
        {"id": "3", "category": "bottoms", "name": "Dark jeans"},
        {"id": "4", "category": "footwear", "name": "White sneakers"},
    ]

    print("Your Sample Wardrobe:")
    for item in sample_wardrobe:
        print(f"  • {item['name']}")

    print("\n\nAnalyzing for: 'Office Professional' occasion...\n")

    analysis = analyze_for_occasion(sample_wardrobe, "office_professional")

    if analysis['has_sufficient_items']:
        print("✅ Your wardrobe is well-equipped for this occasion!")
    else:
        print("⚠️  Your wardrobe has some gaps for this occasion.\n")

        if analysis['missing_essentials']:
            print("Missing Essentials:")
            for item in analysis['missing_essentials'][:3]:
                print(f"  • {item.replace('_', ' ').title()}")

        print(f"\n💡 Gap Reasoning:")
        print(f"   {analysis['gap_reasoning']}")

        if analysis['high_impact_purchases']:
            print(f"\n🎯 High-Impact Purchases (Get these first!):")
            for item in analysis['high_impact_purchases'][:2]:
                print(f"  • {item.replace('_', ' ').title()}")


async def demo_product_search():
    """Demo: Hybrid Product Search."""
    print_header("🛍️  HYBRID PRODUCT SEARCH")

    print("Elara searches across multiple sources in parallel:")
    print("  • Vector Database (existing catalog)")
    print("  • Google Shopping API (real-time)")
    print("  • ASOS API (fashion-specific)")
    print("  • Web Scrapers (Zara, H&M)")
    print("\nAll results are ranked using 8 intelligent signals.\n")

    search_query = "navy blue blazer men's"
    budget = {"soft_cap": 150, "hard_cap": 300}

    print(f"🔍 Searching for: '{search_query}'")
    print(f"💰 Budget: ${budget['soft_cap']}-${budget['hard_cap']}\n")

    print("⏳ Searching across sources...")

    try:
        products = await search_products_hybrid(
            descriptor=search_query,
            budget=budget,
            filters={"gender": "men", "color": "navy"},
            k=5
        )

        if products:
            print(f"\n✅ Found {len(products)} products!\n")

            print("Top 3 Results:\n")
            for i, product in enumerate(products[:3], 1):
                print(f"{i}. {product.title[:65]}")
                print(f"   ${product.price:.2f} at {product.retailer}")
                print(f"   Source: {product.source} | Relevance: {product.relevance_score:.2f}")
                print(f"   {product.url}\n")
        else:
            print("\n⚠️  No products found. This might mean:")
            print("   - Search APIs are not configured (Google Shopping, ASOS)")
            print("   - No products in vector database")
            print("   - Try running: python scripts/seed_products.py\n")

    except Exception as e:
        print(f"\n❌ Search failed: {e}")
        print("   Check if required APIs are configured in .env\n")


async def demo_outfit_generation():
    """Demo: AI Outfit Generation."""
    print_header("🤖 AI OUTFIT GENERATION")

    print("Elara uses GPT-4o to generate personalized outfit recommendations.")
    print("The AI considers:")
    print("  • Your wardrobe items")
    print("  • Current fashion trends")
    print("  • Weather conditions")
    print("  • Occasion and style preferences")
    print("  • Budget constraints")
    print("\n⏳ This would call the LLM to generate 3 outfit options...")
    print("   (Skipped in quick demo to save API costs)")
    print("\nTo test full outfit generation, run:")
    print("   python scripts/test_pipeline.py --e2e\n")


def show_menu():
    """Show interactive menu."""
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "🌟 ELARA AI v2.0 - QUICK DEMO 🌟" + " " * 27 + "║")
    print("╚" + "═" * 78 + "╝")

    print("\nChoose a demo to run:\n")
    print("  1. Fashion Trends Intelligence")
    print("  2. Wardrobe Gap Analysis")
    print("  3. Hybrid Product Search")
    print("  4. AI Outfit Generation")
    print("  5. Run All Demos")
    print("  0. Exit\n")


async def main():
    """Main demo runner."""
    print("\n" + "=" * 80)
    print("  Welcome to Elara AI v2.0!")
    print("  Your intelligent personal styling assistant")
    print("=" * 80)

    while True:
        show_menu()

        try:
            choice = input("Enter your choice (0-5): ").strip()

            if choice == "0":
                print("\nThanks for trying Elara AI! 👋\n")
                break

            elif choice == "1":
                await demo_fashion_trends()
                input("\nPress Enter to continue...")

            elif choice == "2":
                await demo_wardrobe_gap()
                input("\nPress Enter to continue...")

            elif choice == "3":
                await demo_product_search()
                input("\nPress Enter to continue...")

            elif choice == "4":
                await demo_outfit_generation()
                input("\nPress Enter to continue...")

            elif choice == "5":
                await demo_fashion_trends()
                await demo_wardrobe_gap()
                await demo_product_search()
                await demo_outfit_generation()

                print("\n" + "=" * 80)
                print("  ✅ ALL DEMOS COMPLETED!")
                print("=" * 80)

                input("\nPress Enter to continue...")

            else:
                print("\n⚠️  Invalid choice. Please enter 0-5.\n")

        except KeyboardInterrupt:
            print("\n\nDemo interrupted. Goodbye! 👋\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
