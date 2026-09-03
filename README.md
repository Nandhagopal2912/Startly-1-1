# Startly Analyze: Traffic Opportunity Tool

A premium, data-driven SEO intelligence platform for estimating "true demand" from Google SERP data. It moves beyond raw search volume by analyzing SERP real estate saturation and applying sophisticated click-through rate (CTR) penalty models.

![Startly Dashboard](https://github.com/Nandhagopal2912/Startly-1-1/blob/08e160c4b54b59ebdb85111b9632dbd4183f09cc/images/startly-1-1_live_data-1.jpg)
![Startly Dashboard](https://github.com/Nandhagopal2912/Startly-1-1/blob/08e160c4b54b59ebdb85111b9632dbd4183f09cc/images/startly-1-1_live_data-2.jpg)

## 💎 Premium Features

*   **Advanced Dashboard UI**: A modern, high-fidelity interface inspired by Linear and Vercel, featuring glassmorphism, responsive charts, and real-time animations.
*   **Intelligent Growth Verdicts**: Dynamic analysis ascribing categorical opportunity scores (0-100) based on SERP accessibility.
*   **Sophisticated Penalty Modeling**:
    *   **Zero-Click Risk**: Detects AI Overviews and Answer Boxes to penalize volume by up to 45%.
    *   **Commercial Intent**: Identifies Paid Ads and Shopping modules to model transactional value.
    *   **Scalability Metrics**: Calculates adjusted demand per organic slot to judge SEO ROI.
*   **Dual-API Engine**:
    *   **DataForSEO SERP API**: Detailed structure analysis of organic vs. non-organic listings.
    *   **DataForSEO Keywords API**: High-authority search volume retrieval.
*   **Intelligence Logs**: Comprehensive history of analyzed keywords with persistent metrics.
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
Set your `DATAFORSEO_EMAIL` and `DATAFORSEO_PASSWORD`  and `set up it with your won api` in `.env`.

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

Startly Analyze doesn't just show you how many people search for a term—it shows you how many people will actually click on an organic result.

1.  **Raw Volume**: Baseline data from Keywords API.
2.  **SERP Parsing**: Every item on the first page of Google is decomposed by type (Organic vs. Non-Organic).
3.  **Intelligence Modeling**: We apply weighted clickability penalties based on specific SERP modules:
    *   **45% Penalty (High Risk)**: For "Zero-Click" modules like AI Overviews, Knowledge Graphs, and Answer Boxes.
    *   **35% Penalty (Commercial)**: For Google Ads and Shopping results that divert top-of-page traffic.
    *   **20% Penalty (Standard)**: For informational modules like Images, People Also Ask, and Video carousels.
4.  **Adjusted Demand**: The final "True Demand" metric is calculated by applying these penalties to the raw market volume.

---

## 🏗️ Technical Architecture
For detailed information on system design, see [ARCHITECTURE.md](ARCHITECTURE.md).
