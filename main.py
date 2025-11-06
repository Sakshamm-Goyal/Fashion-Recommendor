# main.py
"""
Main orchestrator for Elara AI Personal Stylist.
Coordinates the three-layer pipeline:
1. Deterministic preprocessing
2. LLM reasoning
3. Agentic product matching
4. Deterministic scoring
"""
import asyncio
import json
from deterministic_layer import prepare_input
from llm_reasoning import generate_outfits
from agentic_layer import fetch_buy_links
from scoring_matrix import final_score


def run_session(user_input: dict) -> dict:
    """
    Main entry point for a styling session.

    Args:
        user_input: Raw session input containing:
            - user_profile (preferences, body type, budget)
            - session (location, datetime, occasion, vibe)
            - wardrobe (list of wardrobe items)
            - limits (optional constraints)

    Returns:
        dict with top 3 scored outfit recommendations
    """
    # Phase 1: Deterministic preprocessing
    print("Phase 1: Preparing context...")
    ctx = prepare_input(user_input)

    # Phase 2: LLM reasoning
    print("Phase 2: Generating outfit ideas...")
    llm_out = generate_outfits(ctx)

    # Phase 3: Agentic product matching
    print("Phase 3: Matching products...")
    enriched = asyncio.run(fetch_buy_links(llm_out, ctx))

    # Phase 4: Deterministic scoring
    print("Phase 4: Scoring outfits...")
    results = []

    for rec in enriched["final_recommendations"]:
        # Find corresponding outfit from LLM output
        outfit = next(o for o in enriched["outfits"] if o["name"] == rec["look"])

        # Compute final score
        score = final_score(outfit, rec["items"], ctx)

        # Build result object
        results.append({
            "look": rec["look"],
            "score": score,
            "summary": outfit["summary"],
            "items": rec["items"],
            "reasoning": outfit["reasoning"],
            "tags": outfit["tags"]
        })

    # Sort by score (descending) and return top 3
    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "recommendations": results[:3],
        "context_hash": ctx.get("_hash")
    }


if __name__ == "__main__":
    # Demo payload matching the PRD
    user_input = {
        "user_profile": {
            "gender": "Men",
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
            }
        ],
        "limits": {
            "max_online_items_per_look": 3,
            "retailers_allowlist": ["Zara", "H&M", "ASOS", "Nordstrom", "Macy's", "Amazon Fashion", "Urban Outfitters", "Revolve"]
        }
    }

    print("=" * 60)
    print("ELARA AI PERSONAL STYLIST")
    print("=" * 60)
    print()

    result = run_session(user_input)

    print()
    print("=" * 60)
    print("FINAL RECOMMENDATIONS")
    print("=" * 60)
    print()
    print(json.dumps(result, indent=2))
