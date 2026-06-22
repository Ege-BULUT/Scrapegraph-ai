# TODOs

## Backend Stability
- [x] Fix torchcodec FFmpeg DLL crash at import time (conftest.py mock)
- [x] Fix torchcodec FFmpeg DLL crash at runtime (lazy imports throughout)
- [x] Fix Crawl4aiLoader missing `load()` method
- [x] Fix CamoufoxLoader npx `shell=True` for Windows
- [x] Run 37 experimental backend unit tests — all pass

## epam.com Testing
- [x] Test Playwright — CLOUDFLARE_BLOCKED
- [x] Test Selenium — CLOUDFLARE_BLOCKED
- [x] Test curl_cffi — GOOD (0.2s, 491KB)
- [x] Test Nodriver — CLOUDFLARE_BLOCKED
- [x] Test Crawl4AI — GOOD (45.5s, 721KB)
- [x] Test Camoufox — N/A (no Windows binary)

## Remaining
- [ ] Add `"browser"` top-level config field for backend selection
- [ ] Auto-fallback: browser backends → curl_cffi on Cloudflare
- [ ] Camoufox cookie import API (POST /cookies)
- [ ] e2e tests for all backends
