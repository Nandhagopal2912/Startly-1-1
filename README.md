# Startly Analyze: Traffic Opportunity Tool

An SEO tool that estimates how many searchers would actually click an organic result for a keyword. It reads the live Google results page (AI Overviews, ads, maps, organic links) and applies published click-through-rate data to turn search volume into **capturable organic clicks**, with a range and a per-position breakdown.

![Startly Dashboard](https://github.com/Nandhagopal2912/Startly-1-1/blob/08e160c4b54b59ebdb85111b9632dbd4183f09cc/images/startly-1-1_live_data-1.jpg)
![Startly Dashboard](https://github.com/Nandhagopal2912/Startly-1-1/blob/08e160c4b54b59ebdb85111b9632dbd4183f09cc/images/startly-1-1_live_data-2.jpg)

## 💎 Premium Features

*   **Advanced Dashboard UI**: A modern, high-fidelity interface inspired by Linear and Vercel, featuring glassmorphism, responsive charts, and real-time animations.
*   **Position-Based Click Model**:
    *   **Capturable Clicks**: Monthly organic clicks on page one, shown as an estimate with a low–high range.
    *   **Clicks by Position**: What ranking #1, #2, #3… is worth for this keyword.
    *   **Sourced Effects**: AI Overviews, local packs, image packs and ads reduce clicks by amounts taken from published CTR studies, each labelled with its confidence and source.
    *   **Zero-Click Risk**: Flags pages where Google answers the query itself.
*   **Swappable Data Providers**: SerpApi (detects AI Overviews), Serper, DataForSEO, or a free mock mode, chosen in `.env`.
*   **Cost Guardrails**: Local SQLite cache, remembered volumes, and a daily cap on paid API calls.
*   **Intelligence Logs**: History of analyzed keywords, stored locally and available at `GET /history`.
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

Results are stored in a local SQLite database at `backend/data/startly.db` (created automatically; not committed). Each keyword is fetched again after `CACHE_TTL_DAYS` (default 7). Volumes you type in are remembered, and past analyses are listed at `GET /history`.

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
