#!/usr/bin/env python3
"""
SearXNG to OpenSERP API Adapter

This adapter provides an OpenSERP-compatible API that wraps SearXNG.
It translates OpenSERP API calls to SearXNG format and vice versa.
"""

from flask import Flask, request, jsonify
import requests
from urllib.parse import quote_plus

app = Flask(__name__)

SEARXNG_URL = "http://localhost:8080"  # SearXNG Docker container


@app.route('/mega/engines', methods=['GET'])
def get_engines():
    """Return list of initialized engines (OpenSERP format)"""
    return jsonify({
        "engines": [
            {"initialized": True, "name": "google"},
            {"initialized": True, "name": "bing"},
            {"initialized": True, "name": "duckduckgo"},
        ],
        "total": 3
    })


@app.route('/mega/search', methods=['GET'])
def mega_search():
    """
    OpenSERP-compatible search endpoint.

    Query params:
    - text: Search query
    - engines: Comma-separated list of engines
    - limit: Max results to return

    Returns: List of results in OpenSERP format
    """
    query = request.args.get('text', '')
    engines = request.args.get('engines', 'google,bing,duckduckgo')
    limit = int(request.args.get('limit', 20))

    if not query:
        return jsonify([])

    # Query SearXNG
    try:
        resp = requests.get(
            f"{SEARXNG_URL}/search",
            params={
                'q': query,
                'format': 'json',
                'engines': engines.replace(',', ' ')
            },
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        # Convert SearXNG format to OpenSERP format
        results = []
        for idx, item in enumerate(data.get('results', [])[:limit]):
            results.append({
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'description': item.get('content', ''),
                'engine': item.get('engine', 'unknown'),
                'rank': idx + 1,
                'ad': False
            })

        return jsonify(results)

    except Exception as e:
        print(f"[Adapter] Error querying SearXNG: {e}")
        return jsonify([])


if __name__ == '__main__':
    print("[Adapter] Starting SearXNG to OpenSERP adapter on port 7001...")
    app.run(host='0.0.0.0', port=7001, debug=False)
