# scripts/smoke_demo.py
"""
Smoke test / demo script for Elara AI Personal Stylist.
Runs an end-to-end styling session and prints results.
"""
import os
import sys
import json
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from deterministic_layer import prepare_input
from llm_reasoning import generate_outfits
from agentic_layer import fetch_buy_links
from scoring_matrix import final_score


def demo_payload():
    """
    Returns a demo session payload matching the PRD.
    """
    return {
        "user_profile": {
            "gender": "women",
            "skin_tone": "Olive",
            "brand_prefs": ["Zara", "H&M"],
            "color_prefs": ["Black", "Beige"],
            "body_type": "Athletic",
            "fit_pref": "Slim",
            "style_pref": "Minimalist",
            "budget": {"currency": "USD", "soft_cap": 150, "hard_cap": 300}
        },
        "session": {
            "location": "Soho, New York",
            "datetime_local_iso": "2025-10-05T18:00:00",
            "occasion": "Wedding",
            "vibe": "Chill"
        },
        "wardrobe": [
            {
                "id": "item_000345",
                "brand": "ZARA",
                "name": "Brown open knit collared sweater",
                "category": "Tops",
                "subcategory": "Sweater",
                "dress_codes": ["casual", "dressy casual", "business casual"],
                "seasons": ["fall", "spring", "summer"],
                "colors": ["brown"],
                "fit": "loose",
                "length": "normal",
                "sleeve_length": "short",
                "fabrics": ["crochet"],
                "tags": ["open-knit", "collared", "lightweight"],
                "image": "https://cdn.elara.app/wardrobe/IMG_2381.png",
                "score": 3
            },
            {
                "id": "item_000346",
                "brand": "H&M",
                "name": "Navy cotton chinos",
                "category": "Bottoms",
                "subcategory": "Chinos",
                "dress_codes": ["business casual", "smart casual"],
                "seasons": ["spring", "summer", "fall"],
                "colors": ["navy"],
                "fit": "slim",
                "length": "regular",
                "fabrics": ["cotton"],
                "tags": ["versatile", "classic"],
                "image": "https://cdn.elara.app/wardrobe/IMG_2382.png",
                "score": 4
            }
        ],
        "limits": {
            "max_online_items_per_look": 3,
            "retailers_allowlist": [
                # Primary retailers
                "Zara", "H&M", "ASOS", "Macy's",
                "Amazon Fashion", "Urban Outfitters", "Revolve",
                # Fallbacks (commonly available)
                "Nordstrom", "Bloomingdale's", "Target",
                "DSW", "Anthropologie", "JCPenney"
            ]
        }
    }


def main():
    """
    Main smoke test function.
    """
    print()
    print("=" * 70)
    print(" " * 20 + "ELARA AI PERSONAL STYLIST")
    print(" " * 25 + "Smoke Test Demo")
    print("=" * 70)
    print()

    user_input = demo_payload()

    print("📋 Session Details:")
    print(f"   • Gender: {user_input['user_profile'].get('gender', 'Not specified')}")
    print(f"   • Occasion: {user_input['session']['occasion']}")
    print(f"   • Vibe: {user_input['session']['vibe']}")
    print(f"   • Location: {user_input['session']['location']}")
    print(f"   • Date/Time: {user_input['session']['datetime_local_iso']}")
    print(f"   • Wardrobe Items: {len(user_input['wardrobe'])}")
    print()

    print("─" * 70)
    print("Phase 1: Deterministic Preprocessing")
    print("─" * 70)
    ctx = prepare_input(user_input)
    print(f"✓ Context pack prepared (hash: {ctx['_hash'][:12]}...)")
    print(f"  • Weather: {ctx['weather_compact']['temp_c']}°C, {ctx['weather_compact']['conditions']}")
    print(f"  • Temperature band: {ctx['derived']['temp_band']}")
    print()

    print("─" * 70)
    print("Phase 2: LLM Reasoning (GPT-4o)")
    print("─" * 70)
    print("Generating outfit ideas...")
    llm_out = generate_outfits(ctx)
    print(f"✓ Generated {len(llm_out['outfits'])} outfit recommendations")
    for i, outfit in enumerate(llm_out['outfits'], 1):
        print(f"  {i}. {outfit['name']}")
    print()

    print("─" * 70)
    print("Phase 3: Agentic Product Matching")
    print("─" * 70)
    print("Searching product catalogs and matching items...")
    enriched = asyncio.run(fetch_buy_links(llm_out, ctx))
    print(f"✓ Enriched outfits with product matches")
    print()

    print("─" * 70)
    print("Phase 4: Deterministic Scoring")
    print("─" * 70)
    results = []

    for rec in enriched["final_recommendations"]:
        outfit = next(o for o in enriched["outfits"] if o["name"] == rec["look"])
        score = final_score(outfit, rec["items"], ctx)
        results.append({
            "look": rec["look"],
            "score": score,
            "summary": outfit["summary"],
            "items": rec["items"],
            "reasoning": outfit["reasoning"],
            "tags": outfit["tags"]
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"✓ Scored and ranked {len(results)} outfits")
    print()

    print("=" * 70)
    print(" " * 22 + "FINAL RECOMMENDATIONS")
    print("=" * 70)
    print()

    for i, result in enumerate(results[:3], 1):
        print(f"🎨 LOOK #{i}: {result['look']}")
        print(f"   Score: {result['score']}/10")
        print(f"   {result['summary']}")
        print()
        print("   Items:")
        for item in result["items"]:
            if item["source"] == "wardrobe":
                print(f"     • [Wardrobe] Item {item['wardrobe_item_id']}")
            else:
                print(f"     • [{item['source']}] {item['name']}")
                if item.get('price') and item['price'].get('value'):
                    print(f"       ${item['price']['value']} - {item['buy_link']}")
                else:
                    print(f"       Price: Not available - {item['buy_link']}")
        print()
        print("   Reasoning:")
        for key, value in result["reasoning"].items():
            print(f"     • {key.title()}: {value}")
        print()
        print("   Tags:", ", ".join(result["tags"]))
        print()
        print("─" * 70)
        print()

    print()
    print("=" * 70)
    print(" " * 25 + "SMOKE TEST COMPLETE")
    print("=" * 70)
    print()

    # Also output full JSON for debugging
    output_file = "demo_output.json"
    with open(output_file, "w") as f:
        json.dump({"recommendations": results[:3], "context_hash": ctx["_hash"]}, f, indent=2)
    print(f"💾 Full output saved to: {output_file}")
    print()


if __name__ == "__main__":
    main()
