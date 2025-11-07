# OpenSERP Setup Guide

## Overview

This project uses [OpenSERP](https://github.com/openserp/openserp) for real-time product search through Google Shopping, Bing, and other search engines. OpenSERP provides direct access to search results without API rate limits or costs.

## Quick Start

### 1. Start OpenSERP Server

Before running the demo or application, start the OpenSERP server:

```bash
cd /path/to/openserp
./openserp serve -a 0.0.0.0 -p 7001 &
```

### 2. Verify Server is Running

Check that all engines are initialized:

```bash
curl http://localhost:7001/mega/engines | python3 -m json.tool
```

You should see:
```json
{
  "engines": [
    {"initialized": true, "name": "google"},
    {"initialized": true, "name": "bing"},
    {"initialized": true, "name": "duckduckgo"},
    ...
  ]
}
```

### 3. Run the Application

Once OpenSERP is running, you can run the demo:

```bash
python scripts/smoke_demo.py
```

## Automatic Crash Recovery (OpenSERP Manager)

### Known Issue

OpenSERP has a segmentation fault bug that causes crashes during heavy use. We've implemented an **OpenSERP Manager** to automatically detect and restart crashed servers.

### Limitations

The OpenSERP Manager requires a **long-lived event loop** (e.g., FastAPI, Sanic, or similar async web frameworks). It **does NOT work** with `asyncio.run()` used in demo scripts.

###Usage for Production Apps

If you're using an async web framework with a persistent event loop, enable the manager:

```bash
# In .env file
ENABLE_OPENSERP_MANAGER=true
OPENSERP_BINARY_PATH=/path/to/openserp/openserp
```

The manager will:
- Start OpenSERP server automatically on first product search
- Monitor server health every 30 seconds
- Automatically restart on crashes (up to 3 attempts)
- Log all events for debugging

### Configuration

```bash
# .env file
ENABLE_OPENSERP_MANAGER=false  # true for production apps with persistent event loops
OPENSERP_BINARY_PATH=/path/to/openserp/openserp
OPENSERP_MAX_RESTART_ATTEMPTS=3
OPENSERP_HEALTH_CHECK_INTERVAL=30.0  # seconds
```

## Manual Server Management

For demo scripts and simple applications, manually manage OpenSERP:

**Start server:**
```bash
cd /path/to/openserp && ./openserp serve -a 0.0.0.0 -p 7001 &
```

**Check if running:**
```bash
ps aux | grep openserp
```

**Stop server:**
```bash
pkill -f openserp
```

**Restart after crash:**
```bash
pkill -f openserp
cd /path/to/openserp && ./openserp serve -a 0.0.0.0 -p 7001 &
```

## Troubleshooting

### "Connection Error" during product search

**Cause:** OpenSERP server is not running or crashed

**Solution:**
```bash
# Check if server is running
curl http://localhost:7001/mega/engines

# If not running, start it
cd /path/to/openserp && ./openserp serve -a 0.0.0.0 -p 7001 &
```

### Server crashes frequently

**Cause:** OpenSERP segmentation fault bug

**Short-term:** Restart server manually after each crash

**Long-term:** Use OpenSERP Manager in production app with persistent event loop

### No products found

**Possible causes:**
1. OpenSERP server not running → start server
2. Search query too specific → broaden search terms
3. Rate limiting → add delays between searches

## Architecture

### Current Setup (Demo Scripts)
```
smoke_demo.py
    ↓ asyncio.run()
    ↓
agentic_layer.py
    ↓
product_search_service.py
    ↓
openserp_client.py
    ↓
OpenSERP Server (http://localhost:7001)
```

**Manager Status:** Disabled (incompatible with `asyncio.run()`)

### Production Setup (Web App)
```
FastAPI/Sanic App (persistent event loop)
    ↓
OpenSERP Manager (monitors & restarts server)
    ↓
OpenSERP Server (http://localhost:7001)
    ↓
product_search_service.py
```

**Manager Status:** Enabled with automatic crash recovery

## Implementation Files

- `integrations/openserp_manager.py` - Auto-restart manager
- `integrations/openserp_client.py` - HTTP client for OpenSERP API
- `services/product_search_service.py` - Product search orchestration
- `config.py` - OpenSERP configuration settings

---

**Note:** OpenSERP Manager is production-ready but requires proper application lifecycle management. For simple scripts, use manual server management.
