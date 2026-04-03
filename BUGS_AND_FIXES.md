# BUGS AND FIXES

This document captures the issues faced during development (April 2026) and the exact corrections applied.

## 1. DataForSEO Labs endpoint returning 404

- Symptom:
  - Request to `https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_data/live` returned `404 Not Found`.
  - Logs: `HTTPError: 404 Client Error: Not Found`.

- Root cause:
  - The endpoint was incorrect / unsupported in this API version.

- Fix:
  - Removed `DATAFORSEO_LABS_URL` and `_fetch_labs_volume()` path.
  - Switched to `DATAFORSEO_KEYWORDS_DATA_URL` (`/v3/keywords_data/google/search_volume/live`) for raw volume.

## 2. Wrong payload field for keyword volume API

- Symptom:
  - DataForSEO `status_code: 40501`, and `status_message: "Invalid Field: 'keywords'"` or (similarly) when mismatched.

- Root cause:
  - API expected `keywords` (plural) as an array, not `keyword` singular.

- Fix:
  - `_fetch_search_volume()` now calls:
    ```python
    post_data = [{"keywords": [keyword], "location_name": location_name, "language_name": language_name}]
    ```

## 3. SERP payload keyword_data missing volume by default

- Symptom:
  - `/analyze` results had `raw_volume = 0.0` and `adjusted_volume = 0.0` even when SERP items were present.

- Root cause:
  - `serp/google/organic/live/advanced` response has `keyword_data: {}` (no volume field for some configurations).

- Fix:
  - Keep SERP composition from main endpoint.
  - Use separate search volume endpoint to inject `payload["tasks"][0]["result"][0]["keyword_data"] = {"search_volume": volume}`.

## 4. Outcome

- `/analyze` now returns meaningful volume values and proper saturation + penalty logic.
- `/report` continues to export correct CSV/PDF values.
- Includes easy manual verification via uvicorn logs.
