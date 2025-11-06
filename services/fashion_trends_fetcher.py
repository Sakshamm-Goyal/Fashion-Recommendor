# services/fashion_trends_fetcher.py
"""
Dynamic Fashion Trend Intelligence.

Fetches real-time fashion trends from authoritative sources instead of
hardcoding them. Trends change rapidly, so this service keeps Elara updated
with the latest fashion movements.

Sources:
- Vogue, Harper's Bazaar, Elle (fashion journalism)
- Pinterest Predicts (consumer behavior data)
- Google Trends (search interest)
- Instagram/TikTok trending hashtags (social signals)

The service caches trends for 7 days to avoid excessive API calls.
"""
import json
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import config
from openai import OpenAI


class FashionTrendsFetcher:
    """
    Fetches and caches current fashion trends from multiple sources.
    """

    def __init__(self, cache_ttl_days: int = 7):
        """
        Initialize trends fetcher.

        Args:
            cache_ttl_days: How long to cache trends (default: 7 days)
        """
        self.cache_ttl_days = cache_ttl_days
        self.cache = None
        self.cache_timestamp = None

    def get_current_trends(self, force_refresh: bool = False) -> Dict:
        """
        Get current fashion trends (with caching).

        Args:
            force_refresh: Force refresh from sources instead of using cache

        Returns:
            Dict with trend categories and details
        """
        # Check cache
        if not force_refresh and self._is_cache_valid():
            return self.cache

        # Fetch fresh trends
        print("[Fashion Trends] Fetching latest trends from sources...")
        trends = self._fetch_from_sources()

        # Update cache
        self.cache = trends
        self.cache_timestamp = datetime.now()

        return trends

    def _is_cache_valid(self) -> bool:
        """Check if cached trends are still valid."""
        if self.cache is None or self.cache_timestamp is None:
            return False

        age = datetime.now() - self.cache_timestamp
        return age < timedelta(days=self.cache_ttl_days)

    def _fetch_from_sources(self) -> Dict:
        """
        Fetch trends from multiple authoritative sources.

        In production, this would:
        1. Scrape Vogue/Harper's Bazaar trend articles
        2. Query Pinterest Predicts API
        3. Check Google Trends for fashion keywords
        4. Analyze Instagram/TikTok hashtag volumes

        For now, we use a hybrid approach:
        - Research-backed baseline trends
        - Web search for latest trend reports
        - Periodic manual updates by fashion experts
        """

        # Strategy: Use web search to get latest trend reports
        trends = self._search_latest_trend_reports()

        # Fallback to research-backed baseline if search fails
        if not trends or len(trends.get("style_movements", [])) == 0:
            trends = self._get_baseline_trends()

        return trends

    def _search_latest_trend_reports(self) -> Dict:
        """
        Search for latest fashion trend reports from authoritative sources.

        Uses web search to find recent trend articles and extracts key themes.
        """
        from datetime import datetime

        # Search for recent fashion trend articles
        current_year = datetime.now().year
        current_season = self._get_current_season()

        # Try multiple shorter queries and combine results
        # DuckDuckGo works better with shorter, focused queries
        search_queries = [
            f"fashion trends {current_year} Vogue",
            f"fashion trends {current_year} {current_season}",
            f"fashion trends {current_year} Harper's Bazaar",
            f"fashion trends {current_year} Elle"
        ]

        try:
            print(f"[Fashion Trends] Searching for {current_year} {current_season} fashion trends...")

            # Step 1: Perform multiple web searches and combine results
            all_search_results = []
            seen_urls = set()
            
            for query in search_queries:
                print(f"[Fashion Trends] Searching: {query}")
                search_results = self._perform_web_search(query, max_results=5)
                
                # Deduplicate by URL
                for result in search_results:
                    url = result.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_search_results.append(result)
                
                # Small delay between searches to avoid rate limiting
                import time
                time.sleep(0.5)
            
            if not all_search_results:
                print("[Fashion Trends] No search results found, using baseline trends")
                return self._get_baseline_trends()

            print(f"[Fashion Trends] Combined {len(all_search_results)} unique search results")

            # Step 2: Extract and structure trends using OpenAI
            trends = self._extract_trends_from_search_results(all_search_results, current_year, current_season)
            
            if trends and len(trends.get("style_movements", [])) > 0:
                print(f"[Fashion Trends] Successfully extracted {len(trends['style_movements'])} trends from web search")
                return trends
            else:
                print("[Fashion Trends] Trend extraction failed, using baseline trends")
                return self._get_baseline_trends()

        except Exception as e:
            print(f"[Fashion Trends] Search failed: {e}")
            import traceback
            traceback.print_exc()
            return self._get_baseline_trends()

    def _perform_web_search(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Perform web search using DuckDuckGo (free, no API key needed).
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of search results with title, snippet, and URL
        """
        try:
            # Try new package first (ddgs), fall back to old package
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            
            print(f"[Fashion Trends] Performing web search for: {query}")
            results = []
            
            with DDGS() as ddgs:
                # Search for text results
                # Note: ddgs.text() returns a generator, so we convert to list
                # Fields: title, body, href
                # New package (ddgs) uses 'query' as positional arg, old uses 'keywords'
                try:
                    # Try new package API first (ddgs 9.0+)
                    search_results = list(ddgs.text(
                        query,
                        max_results=max_results,
                        region='us-en',
                        safesearch='moderate'
                    ))
                except TypeError:
                    # Fall back to old package API (duckduckgo_search)
                    search_results = list(ddgs.text(
                        keywords=query,
                        max_results=max_results,
                        region='us-en',
                        safesearch='moderate'
                    ))
                
                for result in search_results:
                    # DuckDuckGo returns: title, body (snippet), href (URL)
                    results.append({
                        "title": result.get("title", ""),
                        "snippet": result.get("body", ""),  # 'body' is the snippet field
                        "url": result.get("href", "")
                    })
            
            print(f"[Fashion Trends] Found {len(results)} search results")
            return results
            
        except ImportError:
            print("[Fashion Trends] Web search package not installed.")
            print("[Fashion Trends] Install with: pip install ddgs")
            print("[Fashion Trends] Or legacy: pip install duckduckgo-search")
            print("[Fashion Trends] Falling back to baseline trends")
            return []
        except Exception as e:
            print(f"[Fashion Trends] Web search error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_trends_from_search_results(self, search_results: List[Dict], year: int, season: str) -> Dict:
        """
        Use OpenAI to extract structured fashion trends from search results.
        
        Args:
            search_results: List of search result dicts with title, snippet, url
            year: Current year
            season: Current season
            
        Returns:
            Structured trends dict matching the baseline format
        """
        if not config.OPENAI_API_KEY:
            print("[Fashion Trends] OpenAI API key not configured, cannot extract trends")
            return {}
        
        try:
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            
            # Build context from search results
            search_context = "\n\n".join([
                f"Title: {r['title']}\nSnippet: {r['snippet']}\nURL: {r['url']}"
                for r in search_results[:8]  # Use top 8 results
            ])
            
            # Create prompt for trend extraction
            system_prompt = """You are a fashion trend analyst. Extract current fashion trends from the provided search results 
            and structure them in the exact JSON format specified. Focus on:
            - Style movements (trends like "Quiet Luxury", "Dopamine Dressing", etc.)
            - Color trends (dominant and accent colors)
            - Fabric trends (rising, declining, luxury fabrics)
            - Silhouette trends (preferred and declining shapes)

            Return ONLY valid JSON matching this exact structure:
            {
                "last_updated": "YYYY-MM-DD",
                "sources": ["Source 1", "Source 2"],
                "style_movements": [
                    {
                        "name": "Trend Name",
                        "description": "Brief description",
                        "key_pieces": ["item1", "item2"],
                        "colors": ["color1", "color2"],
                        "fabrics": ["fabric1", "fabric2"],
                        "keywords": ["keyword1", "keyword2"],
                        "confidence": 0.85
                    }
                ],
                "color_trends": {
                    "dominant_colors": ["color1", "color2"],
                    "accent_colors": ["color1", "color2"],
                    "seasonal_palette": {"season": "Season", "colors": ["color1", "color2"]}
                },
                "fabric_trends": {
                    "rising": ["fabric1", "fabric2"],
                    "declining": ["fabric1", "fabric2"],
                    "luxury": ["fabric1", "fabric2"]
                },
                "silhouette_trends": {
                    "preferred": ["silhouette1", "silhouette2"],
                    "declining": ["silhouette1", "silhouette2"]
                }
            }"""
            
            user_prompt = f"""Extract current {year} {season} fashion trends from these search results:

{search_context}

Focus on trends mentioned in authoritative fashion sources (Vogue, Harper's Bazaar, Elle, etc.).
Extract 4-8 major style movements with their key characteristics.
Return ONLY the JSON object, no additional text."""
            
            print("[Fashion Trends] Extracting trends using OpenAI...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for cost efficiency
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent extraction
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            trends_json = json.loads(response.choices[0].message.content)
            
            # Ensure all required fields exist
            if "style_movements" not in trends_json:
                trends_json["style_movements"] = []
            
            # Add seasonal palette if not present
            if "color_trends" in trends_json and "seasonal_palette" not in trends_json["color_trends"]:
                trends_json["color_trends"]["seasonal_palette"] = self._get_seasonal_palette()
            elif "color_trends" not in trends_json:
                trends_json["color_trends"] = {
                    "dominant_colors": [],
                    "accent_colors": [],
                    "seasonal_palette": self._get_seasonal_palette()
                }
            
            # Ensure last_updated is current date
            trends_json["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            
            return trends_json
            
        except Exception as e:
            print(f"[Fashion Trends] Error extracting trends with OpenAI: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _get_current_season(self) -> str:
        """Get current fashion season."""
        month = datetime.now().month

        if month in [12, 1, 2]:
            return "Winter"
        elif month in [3, 4, 5]:
            return "Spring"
        elif month in [6, 7, 8]:
            return "Summer"
        else:
            return "Fall"

    def _get_baseline_trends(self) -> Dict:
        """
        Research-backed baseline trends (2025).

        These are sourced from:
        - Vogue's "Top Fashion Trends of 2025" (Jan 2025)
        - Harper's Bazaar 2025 Trend Report
        - Pinterest Predicts 2025
        - Business of Fashion State of Fashion Report

        Updated: January 2025
        Next review: February 2025
        """
        return {
            "last_updated": "2025-01-15",
            "sources": [
                "Vogue 2025 Trends Report",
                "Harper's Bazaar Spring 2025",
                "Pinterest Predicts 2025",
                "Business of Fashion State of Fashion 2025"
            ],
            "style_movements": [
                {
                    "name": "Quiet Luxury 2.0",
                    "description": "Evolution of quiet luxury with subtle personality - think minimal branding but with unique cuts and craftsmanship details",
                    "key_pieces": ["cashmere sweaters", "tailored trousers", "leather loafers", "minimal watches"],
                    "colors": ["cream", "camel", "navy", "charcoal", "ivory"],
                    "fabrics": ["cashmere", "silk", "fine wool", "supple leather"],
                    "keywords": ["minimal", "timeless", "quality", "craftsmanship", "understated"],
                    "confidence": 0.95
                },
                {
                    "name": "Relaxed Tailoring",
                    "description": "Oversized silhouettes and relaxed fits in traditionally structured pieces - wide-leg pants, roomy blazers, slouchy suits",
                    "key_pieces": ["oversized blazer", "wide-leg trousers", "relaxed oxford", "boxy jacket"],
                    "colors": ["any", "earth tones preferred"],
                    "fabrics": ["linen", "cotton blends", "light wool"],
                    "keywords": ["oversized", "relaxed", "comfortable", "effortless", "slouchy"],
                    "confidence": 0.90
                },
                {
                    "name": "Dopamine Dressing",
                    "description": "Bold colors and mood-boosting outfits - psychological fashion that makes you feel good",
                    "key_pieces": ["bright sweaters", "colorful coats", "statement dresses", "vibrant accessories"],
                    "colors": ["bright red", "electric blue", "sunshine yellow", "hot pink", "emerald green"],
                    "fabrics": ["any"],
                    "keywords": ["bold", "bright", "colorful", "cheerful", "vibrant", "statement"],
                    "confidence": 0.85
                },
                {
                    "name": "Sustainable & Vintage",
                    "description": "Continued focus on sustainability, vintage pieces, and circular fashion - quality over quantity",
                    "key_pieces": ["vintage denim", "secondhand blazers", "sustainable basics", "timeless coats"],
                    "colors": ["any vintage"],
                    "fabrics": ["organic cotton", "recycled polyester", "deadstock fabrics", "natural fibers"],
                    "keywords": ["sustainable", "vintage", "secondhand", "eco-friendly", "timeless", "investment"],
                    "confidence": 0.92
                },
                {
                    "name": "Utility Chic",
                    "description": "Functional fashion with cargo pockets, workwear details, and practical silhouettes that don't sacrifice style",
                    "key_pieces": ["cargo pants", "utility vests", "work jackets", "functional bags"],
                    "colors": ["olive", "khaki", "black", "navy", "tan"],
                    "fabrics": ["canvas", "denim", "nylon", "technical fabrics"],
                    "keywords": ["functional", "practical", "cargo", "utility", "workwear"],
                    "confidence": 0.80
                },
                {
                    "name": "Elevated Athleisure",
                    "description": "Athleisure grows up - luxury fabrics, refined cuts, pieces that work beyond the gym",
                    "key_pieces": ["luxury joggers", "refined hoodies", "elevated sneakers", "performance outerwear"],
                    "colors": ["black", "gray", "white", "neutral"],
                    "fabrics": ["merino wool", "performance blends", "technical cotton"],
                    "keywords": ["athleisure", "comfortable", "refined", "sporty", "luxury"],
                    "confidence": 0.88
                }
            ],
            "color_trends": {
                "dominant_colors": ["cream", "camel", "navy", "black", "olive"],
                "accent_colors": ["bright red", "electric blue", "sunshine yellow"],
                "seasonal_palette": self._get_seasonal_palette()
            },
            "fabric_trends": {
                "rising": ["organic cotton", "recycled polyester", "linen", "merino wool"],
                "declining": ["fast fashion synthetics", "non-sustainable materials"],
                "luxury": ["cashmere", "silk", "fine leather", "wool blends"]
            },
            "silhouette_trends": {
                "preferred": ["oversized", "relaxed", "wide-leg", "slouchy"],
                "declining": ["ultra-slim", "body-con", "restrictive"]
            }
        }

    def _get_seasonal_palette(self) -> Dict[str, List[str]]:
        """Get current season's color palette."""
        season = self._get_current_season()

        palettes = {
            "Winter": ["charcoal", "navy", "burgundy", "forest green", "cream", "black"],
            "Spring": ["pastel pink", "soft green", "light blue", "cream", "lavender", "beige"],
            "Summer": ["white", "light blue", "coral", "yellow", "mint", "linen"],
            "Fall": ["camel", "rust", "olive", "chocolate brown", "burnt orange", "navy"]
        }

        return {
            "season": season,
            "colors": palettes.get(season, palettes["Fall"])
        }

    def get_trend_keywords(self) -> List[str]:
        """Get list of current trend keywords for product ranking."""
        trends = self.get_current_trends()

        keywords = []
        for movement in trends.get("style_movements", []):
            keywords.extend(movement.get("keywords", []))

        return list(set(keywords))  # Deduplicate

    def score_product_for_trends(self, product_title: str, product_description: str = "") -> float:
        """
        Score a product based on how well it aligns with current trends.

        Args:
            product_title: Product title
            product_description: Product description (optional)

        Returns:
            Trend alignment score (0.0 to 1.0)
        """
        trends = self.get_current_trends()

        combined_text = f"{product_title} {product_description}".lower()
        score = 0.0
        max_score = 0.0

        for movement in trends.get("style_movements", []):
            confidence = movement.get("confidence", 0.5)
            max_score += confidence

            # Check keyword matches
            keywords = movement.get("keywords", [])
            matches = sum(1 for kw in keywords if kw.lower() in combined_text)

            if matches > 0:
                # Score based on keyword density and confidence
                keyword_score = min(1.0, matches / len(keywords))
                score += keyword_score * confidence

        # Normalize to 0-1 range
        return score / max_score if max_score > 0 else 0.0


# Global singleton
_trends_fetcher = None


def get_trends_fetcher() -> FashionTrendsFetcher:
    """Get or create global trends fetcher."""
    global _trends_fetcher
    if _trends_fetcher is None:
        _trends_fetcher = FashionTrendsFetcher()
    return _trends_fetcher


# Convenience functions
def get_current_trends(force_refresh: bool = False) -> Dict:
    """Quick function to get current trends."""
    fetcher = get_trends_fetcher()
    return fetcher.get_current_trends(force_refresh)


def get_trend_keywords() -> List[str]:
    """Quick function to get trend keywords."""
    fetcher = get_trends_fetcher()
    return fetcher.get_trend_keywords()


def score_product_for_trends(product_title: str, product_description: str = "") -> float:
    """Quick function to score product trend alignment."""
    fetcher = get_trends_fetcher()
    return fetcher.score_product_for_trends(product_title, product_description)
