# ScrapeGraphAI Project - Agent Memory

## epam.com Backend Test Results (2026-06-13)

| Backend | Status | Content | Time | Notes |
|---|---|---|---|---|
| **curl_cffi** | ✅ GOOD | 491KB HTML, 42KB text, 333 `<p>`, 47 "EPAM" | 1.6s | TLS fingerprint impersonation bypasses Cloudflare edge check. No JS execution. |
| **Crawl4AI** | ✅ GOOD | 721KB HTML, rich content incl. Vue SPA rendered | 45.5s | Uses Playwright + stealth internally. Gets full JS-rendered content. |
| **Playwright** | ❌ BLOCKED | 36KB (Cloudflare Turkish challenge) | 6.1s | Malenia stealth + persistent profile not enough for epam.com Turnstile |
| **Selenium** | ❌ BLOCKED | 34KB (Cloudflare Turkish challenge) | 23.9s | undetected-chromedriver also blocked |
| **Nodriver** | ❌ BLOCKED | 34KB (Cloudflare Turkish challenge) | 7.0s | CDP-based, still detected |
| **Camoufox** | ❌ N/A | N/A | N/A | Firefox fork (daijro/camoufox) has no Windows binary — Linux/macOS only |

## Issues Found & Fixed

### torchcodec FFmpeg DLL crash (module import time & runtime)
- Root cause: `sentence_transformers` → `torchcodec` → FFmpeg native DLLs not loadable on this system
- Fix: All docloaders + experimental loaders use lazy `Document` imports + avoid `BaseLoader` inheritance
- `docloaders/__init__.py` + `experimental/__init__.py`: lazy `__getattr__` pattern
- `tests/conftest.py`: mocks `torchcodec` as no-op module with proper `ModuleSpec`
- Fixed files: `chromium.py`, `plasmate.py`, `fetch_node.py`, `robots_node.py`, `docloaders/__init__.py`, `crawl4ai_loader.py`, `obscura_loader.py`, `camoufox_loader.py`

### Crawl4aiLoader missing load() method
- Had `lazy_load()` and `alazy_load()` but NOT `load()`
- `fetch_node.py` calls `loader.load()` on all experimental backends
- Fix: Added `def load(self) -> list: return list(self.lazy_load())`

### CamoufoxLoader npx not found on Windows
- npx is `npx.CMD` on Windows; `subprocess.run` without `shell=True` can't find `.CMD` files via `CreateProcess`
- Fix: Added `shell=True` to all `_check_npx()` and `_start_server()` subprocess calls
- Fixed file: `camoufox_loader.py`

### Camoufox binary not available on Windows
- daijro/camoufox GitHub releases only ship Linux + macOS binaries (no Windows)
- camofox-browser npm package can install but can't start browser on Windows
- Possible workaround: Docker container, WSL2, or Linux VM

## Key System Characteristics
- Python 3.13.7
- Windows (win32)
- Node.js v24.10.0 available
- Chromium-based browsers only (Playwright's bundled or system Chrome)
- epam.com uses Cloudflare Turnstile + Vue.js SPA

## Working Backends
1. **curl_cffi** (chrome124 TLS impersonation) — fastest, bypasses CF, no JS
2. **Crawl4AI** (Playwright + stealth) — full JS rendering, bypasses CF via Playwright fallback
3. **Playwright** (system Chrome + Malenia) — blocked by CF but good with cookie cache after manual solve
4. **Selenium** (undetected-chromedriver) — blocked by CF
5. **Nodriver** (CDP direct) — blocked by CF
6. **Camoufox** — Linux/macOS only

## Test Command
```bash
python -m pytest tests/test_experimental_backends.py -q --tb=line
# 37 passed, 9 warnings in ~30s
```
