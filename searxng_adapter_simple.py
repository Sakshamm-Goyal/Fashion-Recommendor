#!/usr/bin/env python3
"""
SearXNG to OpenSERP API Adapter (using stdlib only)

This adapter provides an OpenSERP-compatible API that wraps SearXNG.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote_plus
import urllib.request
import json

SEARXNG_URL = "http://localhost:8080"


class AdapterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress request logging

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/mega/engines':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "engines": [
                    {"initialized": True, "name": "google"},
                    {"initialized": True, "name": "bing"},
                    {"initialized": True, "name": "duckduckgo"},
                ],
                "total": 3
            }
            self.wfile.write(json.dumps(response).encode())

        elif path == '/mega/search':
            query = params.get('text', [''])[0]
            engines = params.get('engines', ['google,bing,duckduckgo'])[0]
            limit = int(params.get('limit', ['20'])[0])

            if not query:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'[]')
                return

            try:
                # Query SearXNG
                searxng_engines = engines.replace(',', ' ')
                url = f"{SEARXNG_URL}/search?q={quote_plus(query)}&format=json&engines={quote_plus(searxng_engines)}"

                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode())

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

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(results).encode())

            except Exception as e:
                print(f"[Adapter] Error: {e}")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'[]')

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == '__main__':
    port = 7001
    print(f"[Adapter] Starting SearXNG to OpenSERP adapter on port {port}...")
    print(f"[Adapter] Proxying to SearXNG at {SEARXNG_URL}")
    server = HTTPServer(('0.0.0.0', port), AdapterHandler)
    server.serve_forever()
