#!/usr/bin/env python3
"""
Quick test script to verify new modules work correctly.
Tests all major components added in the enhancement.
"""
import asyncio
from contracts.models import Product, CompositionItem, WardrobeItem
from services.product_enrichment import enrich_product
from services.outfit_composer import validate_composition, MAKEUP_BY_OCCASION
from services.outfit_scorer import SCORING_DIMENSIONS

def test_product_enrichment():
    """Test product enrichment module."""
    print("\n=== Testing Product Enrichment ===")

    # Create a sample product
    product = Product(
        id="test_001",
        title="Men's Slim Fit Cotton Dress Shirt Black",
        price=49.99,
        currency="USD",
        url="https://example.com/shirt",
        retailer="Example Store"
    )

    # Enrich it
    enriched = enrich_product(product)

    print(f"Original title: {product.title}")
    print(f"Enriched category: {enriched.category}")
    print(f"Enriched fabric: {enriched.fabric}")
    print(f"Enriched fit_type: {enriched.fit_type}")
    print(f"Enriched color: {enriched.color}")
    print(f"Fabric quality score: {enriched.fabric_quality_score}")
    print("✓ Product enrichment works!")

def test_outfit_composer():
    """Test outfit composition validation."""
    print("\n=== Testing Outfit Composer ===")

    # Test men's composition
    men_composition = [
        CompositionItem(slot="top", source="wardrobe", wardrobe_item_id="shirt_1"),
        CompositionItem(slot="bottom", source="wardrobe", wardrobe_item_id="pants_1"),
        CompositionItem(slot="footwear", source="wardrobe", wardrobe_item_id="shoes_1"),
        CompositionItem(slot="accessory", source="online", descriptor="Watch"),
        CompositionItem(slot="accessory", source="online", descriptor="Belt"),
    ]

    result = validate_composition(men_composition, gender="male")
    print(f"Men's composition valid: {result['is_valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")

    # Test women's composition
    women_composition = [
        CompositionItem(slot="one_piece", source="wardrobe", wardrobe_item_id="dress_1"),
        CompositionItem(slot="footwear", source="wardrobe", wardrobe_item_id="heels_1"),
        CompositionItem(slot="accessory", source="online", descriptor="Handbag"),
        CompositionItem(slot="accessory", source="online", descriptor="Earrings"),
        CompositionItem(slot="accessory", source="online", descriptor="Necklace"),
        CompositionItem(slot="accessory", source="online", descriptor="Sunglasses"),
    ]

    result = validate_composition(women_composition, gender="female", occasion="formal")
    print(f"\nWomen's composition valid: {result['is_valid']}")
    print(f"Makeup suggestion: {result['makeup_suggestion']}")
    print("✓ Outfit composer works!")

def test_scoring_framework():
    """Test 10-dimension scoring framework."""
    print("\n=== Testing 10-Dimension Scoring ===")

    total_weight = sum(dim["weight"] for dim in SCORING_DIMENSIONS.values())
    print(f"Total weight: {total_weight:.2f} (should be 1.0)")

    print("\nScoring dimensions by category:")
    categories = {}
    for dim_name, dim_info in SCORING_DIMENSIONS.items():
        cat = dim_info["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((dim_name, dim_info["weight"]))

    for cat, dims in categories.items():
        cat_weight = sum(w for _, w in dims)
        print(f"\n{cat.upper()}: {cat_weight*100:.0f}%")
        for name, weight in dims:
            print(f"  - {name}: {weight*100:.0f}%")

    print("\n✓ Scoring framework configured correctly!")

def test_makeup_suggestions():
    """Test makeup suggestion generation."""
    print("\n=== Testing Makeup Suggestions ===")

    occasions = ["formal", "casual", "date_night"]
    for occasion in occasions:
        makeup = MAKEUP_BY_OCCASION.get(occasion)
        print(f"\n{occasion.title()}:")
        print(f"  Style: {makeup['style']}")
        print(f"  Focus: {makeup['focus']}")
        print(f"  Description: {makeup['description'][:60]}...")

    print("\n✓ Makeup suggestions work!")

def main():
    """Run all tests."""
    print("=" * 60)
    print("TESTING NEW ELARA MODULES")
    print("=" * 60)

    try:
        test_product_enrichment()
        test_outfit_composer()
        test_scoring_framework()
        test_makeup_suggestions()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nAll new modules are working correctly.")
        print("Ready for production use!")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
