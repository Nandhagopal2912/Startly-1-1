# Traffic Opportunity Tool

Full-stack app for estimating "true demand" from Google SERP data with DataForSEO Regular Organic API.

## Features

- FastAPI backend with `/analyze` endpoint.
- Local caching in `backend/cache/` to avoid repeated paid API calls.
- Mock mode for safe UI testing without billing.
- Penalty rule: if any SERP item is non-organic, adjusted volume = raw volume * 0.7.
- Saturation score: `organic_results / total_results`.
- CSV/PDF report export from backend `/report`.
- Next.js App Router UI with Tailwind + Chart.js.
- Standalone Python extractor script for large JSON files.

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
