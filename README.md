# Startly Analyze: Traffic Opportunity Tool

An SEO tool that estimates how many searchers would actually click an organic result for a keyword. It reads the live Google results page (AI Overviews, ads, maps, organic links) and applies published click-through-rate data to turn search volume into **capturable organic clicks**, with a range and a per-position breakdown.

![Startly Dashboard](https://github.com/Nandhagopal2912/Startly-1-1/blob/08e160c4b54b59ebdb85111b9632dbd4183f09cc/images/startly-1-1_live_data-1.jpg)
![Startly Dashboard](https://github.com/Nandhagopal2912/Startly-1-1/blob/08e160c4b54b59ebdb85111b9632dbd4183f09cc/images/startly-1-1_live_data-2.jpg)

## 💎 Premium Features

*   **Advanced Dashboard UI**: A modern, high-fidelity interface inspired by Linear and Vercel, featuring glassmorphism, responsive charts, and real-time animations.
*   **Clear Verdicts and Next Steps**: Each keyword gets a verdict (worth targeting, modest, or low potential) from what the top positions are worth, plus recommended actions based on what Google shows: AI Overviews, maps, ads, People Also Ask and more.
*   **Who Ranks Now**: The sites on page one, with the monthly clicks each position should get.
*   **Edit Volume Any Time**: Add or change a keyword's monthly volume on the dashboard; it re-scores the saved page without an API call.
*   **Country Targeting**: Analyze for 18 countries.
*   **Position-Based Click Model**:
    *   **Capturable Clicks**: Monthly organic clicks on page one, shown as an estimate with a low–high range.
    *   **Clicks by Position**: What ranking #1, #2, #3… is worth for this keyword.
    *   **Sourced Effects**: AI Overviews, local packs, image packs and ads reduce clicks by amounts taken from published CTR studies, each labelled with its confidence and source.
    *   **Zero-Click Risk**: Flags pages where Google answers the query itself.
*   **Bulk Analysis**: Paste up to 50 keywords (optionally with volumes), see how many API calls the batch needs before running it, and get them ranked by capturable clicks.
*   **Swappable Data Providers**: SerpApi (detects AI Overviews), Serper, DataForSEO, or a free mock mode, chosen in `.env`.
*   **Cost Guardrails**: Local SQLite cache, remembered volumes, and a daily cap on paid API calls.
*   **SERP Change Tracking**: Re-check a keyword to fetch Google's page again and see what changed since the last check: features that appeared or disappeared, sites that moved, and the effect on capturable clicks.
*   **Saved History**: Every analysis is stored locally. The dashboard restores your recent keywords after a refresh, and the History page lets you search and reopen any past analysis without API calls.
*   **Professional Reporting**: Integrated PDF and CSV export engine for stakeholder presentations.

## 🚀 Quick Start

### 1) Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
```
Choose a data source in `.env`:
- `SERP_PROVIDER=serpapi` with a free `SERPAPI_API_KEY` from [serpapi.com](https://serpapi.com) (250 searches/month). **Recommended:** it is the only free option here that detects AI Overviews, or
- `SERP_PROVIDER=serper` (default) with a free `SERPER_API_KEY` from [serper.dev](https://serper.dev). It is cheaper, but it doesn't return AI Overviews, so their effect on clicks is never applied, or
- `SERP_PROVIDER=dataforseo` with `DATAFORSEO_EMAIL` and `DATAFORSEO_PASSWORD`, or
- `SERP_PROVIDER=mock` to develop without any key.

Serper doesn't provide search volume, so type it into the **Volume** box (for example, from Google Keyword Planner), or set `VOLUME_PROVIDER=dataforseo`. `MAX_API_CALLS_PER_DAY` (default 50) stops a bug from draining your credits.

Results are stored in a local SQLite database at `backend/data/startly.db` (created automatically; not committed). Each keyword is fetched again after `CACHE_TTL_DAYS` (default 7). Volumes you type in are remembered. Past analyses are on the **History** page (`GET /history`, `GET /history/{id}`).

Run the tests (no API calls, no keys needed):
```bash
pip install -r requirements-dev.txt
pytest
```

Run the API:
```bash
uvicorn main:app --reload --port 8000
```

### 2) Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000).

## 🌐 Running a Public Demo

Startly is built to run on your own machine. Before putting it online, run the backend in **demo mode**, so visitors can't spend your API credits or change your data:

| Setting (`backend/.env`) | Value for a public demo | What it does |
| :--- | :--- | :--- |
| `DEMO_MODE` | `true` | Serves only saved analyses; no provider calls, no database writes. Unknown keywords, re-checks and mock analyses are refused. Volume edits apply to that response only. |
| `ALLOWED_ORIGINS` | your frontend URL | Only your site's pages can call the API. |
| `RATE_LIMIT_PER_MINUTE` | e.g. `60` | Per-IP request limit (`429` with `Retry-After` when exceeded). |
| `TRUST_PROXY_HEADERS` | `true` behind a hosting proxy | Rate-limits the real client IP from `X-Forwarded-For`. |

Fill the demo database first by analyzing your sample keywords locally (with your key), then deploy that `backend/data/startly.db` with `DEMO_MODE=true`. Use a fresh database with only the samples you want to show. Mock analyses also appear in History.

**Visitors can use their own key.** In the demo, anyone can explore the samples for free, or add their own free [SerpApi](https://serpapi.com) key to analyze any keyword:
- The key stays in their browser and is sent only with their own searches, in an `X-SerpApi-Key` header. The server uses it for that request and never stores or logs it.
- Their results are saved **in their browser** (with the results page), so reopening, editing volume (`POST /rescore`) and comparing re-checks need no further searches, and nobody else can see them.
- `POST /key/check` validates a key and shows searches left, using SerpApi's free account endpoint.
- These searches use the visitor's quota, not yours, and don't count toward `MAX_API_CALLS_PER_DAY`.

Never deploy with `DEMO_MODE=false` and your own API key: anyone could use your credits.

## 🧠 Methodology

Startly shows how many people would actually click an organic result, not just how many search.

1.  **Search volume**: Entered by you or fetched from DataForSEO.
2.  **SERP parsing**: Every item on Google's first page is classified (organic, AI Overview, ads, local pack, images, People Also Ask…).
3.  **Baseline click curve**: The share of searches that click each organic position, from [Advanced Web Ranking's CTR study](https://www.advancedwebranking.com/seo/organic-ctr) (19.4% at #1 down to 0.8% at #10).
4.  **Feature effects**: Features that measurably take clicks scale the positions they affect. For example, an AI Overview cuts position 1 by about 52%. People Also Ask and videos carry no penalty, because the data shows none.
5.  **Range**: Overlapping features are combined two ways (stacked vs strongest only) to give a low–high range around the estimate.

For example, "what is a roth ira" at 10,000 searches a month comes out at about **2,060 capturable clicks (range 1,919–2,200)**.

The full method, every number and its source, a worked example and the limitations are in **[METHODOLOGY.md](METHODOLOGY.md)**.

---

## 🏗️ Technical Architecture
For detailed information on system design, see [ARCHITECTURE.md](ARCHITECTURE.md).
