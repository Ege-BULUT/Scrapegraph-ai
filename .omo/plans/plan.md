# Work Plan — ScrapeGraphAI Experimental Backends

## Goal
Add multiple stealth browser backends (Camoufox, NoDriver, curl_cffi, undetected-chromedriver, Crawl4AI) to ScrapeGraphAI for Cloudflare bypass, with auto-configuration via `launcher.py`.

## Progress

### ✅ Done
- **CamoufoxLoader** — REST API wrapper for camofox-browser (Firefox fork with C++ anti-detection)
- **Crawl4aiLoader** — Crawl4AI backend with Playwright stealth fallback
- **NoDriver backend** — CDP-based async browser via `nodriver`
- **curl_cffi backend** — HTTP-level TLS fingerprint impersonation (`chrome124`)
- **undetected-chromedriver backend** — Selenium-based with thread pool executor
- **ObscuraLoader** — CDP connection via Playwright `connect_over_cdp`
- **`launcher.py`** — Auto-installs deps, checks Chrome/Node.js, creates persistent dirs
- **`fetch_node.py`** — Routes to experimental backends via `"experimental"` config
- **`experimental/__init__.py`** — Lazy `__getattr__` pattern prevents torchcodec DLL crash
- **`tests/conftest.py`** — Mocks `torchcodec` as no-op for test collection
- **torchcodec runtime fix** — `chromium.py`, `plasmate.py`, `docloaders/__init__.py`, `fetch_node.py`, `robots_node.py` all use lazy imports
- **Crawl4aiLoader `load()` fix** — Added missing `load()` method
- **CamoufoxLoader Windows fix** — Added `shell=True` for npx calls (npx.CMD compat)
- **37 unit tests** — All passing

### 🔲 Next
- [ ] Add `"browser"` field to top-level config (like `"llm"`) for backend selection
- [ ] Add Camoufox cookie import API (POST /cookies) for authenticated sessions
- [ ] Auto-fallback: when Playwright detects Cloudflare, retry with curl_cffi
- [ ] e2e tests against epam.com for all backends
- [ ] Firefox-Stealth backend (feder-cr/firefox-stealth, 15 C++ patches)

## Key Findings
- **curl_cffi** bypasses Cloudflare for epam.com (TLS fingerprint, 0.2s)
- **Crawl4AI** gets full JS-rendered content (721KB, 45.5s)
- Playwright/Selenium/Nodriver all blocked by Cloudflare Turnstile
- **Camoufox** has no Windows binary — Linux/macOS only
- torchcodec crash fixed via lazy imports throughout the import chain

## Test Command
```bash
python -m pytest tests/test_experimental_backends.py -q --tb=line
```
