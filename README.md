# Traffic Opportunity Tool

Full-stack app for estimating "true demand" from Google SERP data with DataForSEO Regular Organic API.

![image alt](https://github.com/Nandhagopal2912/Startly-1-1/blob/c2b9e988e47023a6e27bff21ea33ab5d7a61b777/images/startly-1-1_live_data-1.jpg
)

![image alt](https://github.com/Nandhagopal2912/Startly-1-1/blob/c2b9e988e47023a6e27bff21ea33ab5d7a61b777/images/startly-1-1_live_data-2.jpg
)

![image alt](https://github.com/Nandhagopal2912/Startly-1-1/blob/c2b9e988e47023a6e27bff21ea33ab5d7a61b777/images/startly-1-1_live_data-3jpg.jpg)

## Features

The Traffic Opportunity Tool combines SERP analysis and keyword intent scoring into a single workflow:

- FastAPI backend with `/analyze` and `/report` endpoints.
- Uses DataForSEO Google Organic SERP API for result classification.
- Uses DataForSEO Keywords Data API for authoritative search volume.
- Caching in `backend/cache/` to reduce repeated API calls and cost.
- `mock_mode` for safe UI development without hitting external APIs.
- SERP saturation analysis:
  - `saturation_score = organic_results / total_results`
  - `saturation_label` in three tiers (high organic share/mixed SERP/SERP-heavy-non-organic).
- Non-organic penalty:
  - If any result is non-organic (e.g., snippets, PAA, videos), adjusted volume = `raw_volume * 0.7`.
- CSV/PDF reporting with `POST /report`.
- Next.js + Tailwind UI with interactive result cards and charts.
- Includes CLI JSON extractor script for offline dataset processing.

## Bug-fix notes

See [BUGS_AND_FIXES.md](BUGS_AND_FIXES.md) for all issues resolved in this release.

## 1) Python extractor script (special instruction)

```bash
cd backend/scripts
python extract_serp_fields.py --input input.json --output extracted.json
python extract_serp_fields.py --input input.json --csv extracted.csv
```

Extracted fields per item:

- `domain`
- `type`
- `rank_group`

## 2) Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set real credentials in `.env`:

```env
DATAFORSEO_LOGIN=...
DATAFORSEO_PASSWORD=...
```

Run API:

```bash
uvicorn main:app --reload --port 8000
```

## 3) Frontend setup

```bash
cd frontend
npm install
```

Optional environment for API base URL:

```bash
set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Run UI:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## API Contract

### `POST /analyze`

Request:

```json
{
  "keyword": "best running shoes",
  "location_name": "United States",
  "language_name": "English",
  "mock_mode": true
}
```

### `POST /report`

Request:

```json
{
  "format": "csv",
  "rows": [
    {
      "keyword": "best running shoes",
      "raw_volume": 10000,
      "adjusted_volume": 7000,
      "saturation_score": 0.8
    }
  ]
}
```
