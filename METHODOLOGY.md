# Methodology

Startly estimates how many people would actually click an organic result for a keyword. It doesn't report raw search volume as the opportunity. Google's results page now holds AI Overviews, ads, maps and other features that take clicks before a searcher reaches the organic links. Startly measures what is on the page and applies published click-through-rate (CTR) data to it.

The result is **capturable organic clicks**: an estimate, with a low–high range, of the monthly clicks available to organic results on page one, and how they split by ranking position.

All model numbers live in [`backend/ctr_config.py`](backend/ctr_config.py), each with its source. The calculation is in [`backend/ctr_model.py`](backend/ctr_model.py).

## 1. Inputs

| Input | Where it comes from |
|---|---|
| **SERP snapshot** | One live Google results page per keyword from SerpApi, Serper or DataForSEO (`SERP_PROVIDER`). Each item is classified by type: `organic`, `ai_overview`, `paid`, `local_pack`, `images`, `people_also_ask`, and so on. |
| **Monthly search volume** | Typed in by the user (for example, from Google Keyword Planner), or from DataForSEO when `VOLUME_PROVIDER=dataforseo`. Every result records where its volume came from. |

Only SerpApi and DataForSEO report AI Overviews. Serper doesn't, so with `SERP_PROVIDER=serper` the AI Overview effect is never applied.

## 2. Baseline click curve

The starting point is the share of searches that click each organic position on an average results page:

| Position | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **CTR %** | 19.38 | 9.64 | 6.02 | 3.88 | 2.68 | 1.86 | 1.37 | 1.10 | 0.94 | 0.81 |

Source: [Advanced Web Ranking (AWR) CTR study](https://www.advancedwebranking.com/seo/organic-ctr), Google US, all devices, unbranded queries, July 2026. AWR builds it from more than 1.75 million US results pages a month, with impression-weighted CTR per position.

Unbranded data was chosen because Startly is used to evaluate keywords a site doesn't already own. Branded queries have much higher CTRs (27.3% at position 1).

On a page with ten organic results and no other features, page one sends organic clicks on about **47.7%** of searches. The other searches click something else, refine the query, or leave without clicking.

## 3. SERP feature effects

Each feature present on the page scales the CTR of specific positions:

| Feature | Effect | Confidence | Source |
|---|---|---|---|
| **AI Overview** | ×0.48 at #1, ×0.36 at #2, ×0.44 at #3, ×0.74 at #4, ×0.94 at #5, ×0.72–0.87 at #6–10 | High | AWR July 2026: desktop CTR with an AI Overview divided by overall desktop CTR, per position (position 1: 9.69% vs 20.02%). [Ahrefs](https://ahrefs.com/blog/ai-overviews-reduce-clicks-update/) measured a similar drop, about 58% at position 1, from Search Console data for 300,000 keywords (December 2023 vs December 2025). |
| **Local pack (map)** | ×0.06 at #1 | Medium | AWR July 2026: position 1 CTR −94% when a local pack is present (desktop) |
| **Image pack** | ×0.74 at #1 | Medium | AWR July 2026: position 1 CTR −26% when images are present (desktop) |
| **Top ads** | ×0.70 at #1 | **Low** | [AWR/Caphyon 2014](https://www.advancedwebranking.com/blog/google-organic-ctr): position 1 CTR 25.7% without ads vs 17.9% with ads. No recent primary study was found. |

"Medium" means the effect is measured only at position 1. Positions without data are left unchanged.

### Features with no penalty

| Feature | Why there's no penalty |
|---|---|
| People Also Ask | AWR finds position 1 CTR is not lower (+43%) when it's present |
| Videos | AWR finds position 1 CTR is not lower when they're present |
| Knowledge panel | AWR finds about the same position 1 CTR (+5%) |
| Featured snippet, direct answer box, shopping, top stories | No reliable current data. Neutral until measured. |

AWR's positive numbers for People Also Ask and videos most likely reflect the kinds of queries that show those features, not a click boost from the features themselves. Startly treats them as neutral rather than as a bonus.

## 4. Combining features: the range

When several features appear together, their effects overlap: an AI Overview and ads often sit on the same page. The data doesn't say exactly how they combine, so Startly calculates two bounds for every position:

- **Low estimate:** every feature's multiplier stacks (CTR × m₁ × m₂ × …). This assumes the effects are independent.
- **High estimate:** only the strongest multiplier applies (CTR × min(m₁, m₂, …)). This assumes the effects fully overlap.
- **Estimate:** the midpoint of the two.

AWR's measured combinations sit close to the stacked bound. AI Overview plus local pack measured −97% at position 1, and stacking gives −97%. The range therefore leans conservative.

The source data is noisy at lower positions; AWR's AI Overview figures rise slightly between #8 and #9, for example. Each curve is smoothed so a lower position never gets a higher CTR than the one above it.

Positions are counted only up to the number of organic results actually on the page, with a maximum of 10.

## 5. Outputs

| Output | Meaning |
|---|---|
| **Capturable clicks** | Volume × sum of the adjusted CTRs for the organic positions on the page, shown with its low–high range |
| **Clicks by position** | The same figure per position: "ranking #3 here ≈ 263 clicks a month" |
| **Clicks kept / click loss %** | Adjusted CTR total compared with a plain page that has the same number of organic results |
| **Organic share** | Organic results ÷ all page-one items. Describes the layout; it doesn't affect the click estimate. |
| **Click access tier** | Open (< 25% click loss), Contested (25–50%), Click-hostile (> 50%) |
| **Verdict** | "Worth targeting" when the top three positions together are worth at least 500 clicks a month. The threshold is a product choice, not a measured value. |

With no search volume, Startly reports CTR percentages instead of click counts.

## 6. Worked example: "what is a roth ira"

SerpApi returned 6 organic results, an AI Overview, ads, People Also Ask and a video. Volume: 10,000 a month (entered by the user).

| Position | Baseline | Low (stacked) | High (strongest only) | Estimate |
|---|---|---|---|---|
| #1 | 19.38% | 19.38 × 0.48 × 0.70 = 6.6% → 657 | 19.38 × 0.48 = 9.4% → 938 | **797** |
| #2 | 9.64% | × 0.36 → 343 | 343 | **343** |
| #3 | 6.02% | × 0.44 → 263 | 263 | **263** |
| #4 | 3.88% | × 0.74 = 2.9%, smoothed to 2.6% → 263 | 263 | **263** |
| #5 | 2.68% | × 0.94 → 253 | 253 | **253** |
| #6 | 1.86% | × 0.75 → 140 | 140 | **140** |
| **Total** | | **1,919** | **2,200** | **≈ 2,060** |

People Also Ask and the video change nothing. A plain page with six organic results would send about 4,346 clicks, so these features remove about 53%. Startly's earlier flat-penalty model reported 5,500 for the same keyword.

This example uses the results page from October 21, 2026. A re-check on October 24 found no ads and seven organic results, so the estimate rose to about 2,305 clicks with no range (one feature left, so stacked and strongest-only agree). That is what the demo shows. Results pages change, so every estimate belongs to the date of its snapshot.

## 7. Limitations

- **Averages, not this keyword.** The curves average millions of results pages. A single keyword can differ by 2× or more because of intent, brand strength, title quality or device mix. The model is most reliable for **comparing** keywords, since the same assumptions apply to all of them.
- **Volume drives everything.** Click counts scale directly with the volume input, and Keyword Planner volumes are often wide ranges.
- **Mixed segments.** The baseline is unbranded and all devices; the AI Overview multipliers are from desktop data.
- **Old ads data.** The ads effect comes from a 2014 study and is flagged as low confidence wherever it's used.
- **Correlation.** The feature studies are observational. Pages with AI Overviews may differ in other ways, such as query type.
- **No ranking difficulty.** Startly estimates what a position is worth, not how hard it is to reach.
- **Not yet validated against real clicks.** The roadmap adds a Search Console import so users with sites can compare estimates with their real data.

## 8. Changing the model

1. Edit [`backend/ctr_config.py`](backend/ctr_config.py). Update `BASELINE_CTR`, change a feature's `multipliers`, or move a feature between `FEATURES` and `NEUTRAL_FEATURES`. Keep the `source`, `url` and `confidence` fields accurate.
2. Run the tests from `backend/`:

   ```bash
   pytest tests/test_ctr_model.py
   ```

   `test_position_1_matches_awr_measurements` checks position 1 against AWR's measured effects. Update its expected values if you change data sources.
3. Old analyses in history keep the numbers they were calculated with. Re-analyzing a cached keyword re-scores it with the new model at no API cost.

## Sources

- Advanced Web Ranking, [Google Organic CTR study](https://www.advancedwebranking.com/seo/organic-ctr): figures used are from July 2026 (opened October 2026).
- Ahrefs, [Update: AI Overviews Reduce Clicks by 58%](https://ahrefs.com/blog/ai-overviews-reduce-clicks-update/).
- Advanced Web Ranking / Caphyon, [Google Organic CTR, 2014 report](https://www.advancedwebranking.com/blog/google-organic-ctr).
