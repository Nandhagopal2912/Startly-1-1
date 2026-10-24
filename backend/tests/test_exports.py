import csv
import io

from fastapi.testclient import TestClient

from conftest import load_fixture

from main import app
from providers.serpapi import normalize as serpapi_normalize
from scoring import analyze_payload

client = TestClient(app)


def roth_row(volume=10000, **extra):
    """A dashboard row like the frontend sends: the analysis plus its display fields."""
    snapshot = serpapi_normalize(load_fixture("serpapi_roth_ira.json"), "what is a roth ira")
    analysis = analyze_payload(snapshot, "what is a roth ira", volume_override=volume)
    return {**analysis, "source": "cache", "provider": "serpapi", "location_name": "United States",
            "analyzed_at": "2026-10-24T06:56:20+00:00", **extra}


def plain_row(keyword, volume):
    snap = {"keyword": keyword, "provider": "serpapi", "keyword_data": {},
            "items": [{"type": "organic", "domain": f"{keyword[:3]}{i}.com", "rank_group": i} for i in range(1, 11)]}
    return {**analyze_payload(snap, keyword, volume_override=volume), "provider": "serpapi", "location_name": "India"}


def read_csv(res):
    assert res.status_code == 200
    text = res.content.decode("utf-8")
    assert text.startswith("﻿")  # BOM so Excel reads UTF-8
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


def test_keywords_csv_is_one_ranked_row_per_keyword():
    rows = [plain_row("small kw", 500), roth_row(), plain_row("big kw", 50000)]
    res = client.post("/report", json={"rows": rows, "format": "csv"})
    table = read_csv(res)

    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="startly-keywords-' in res.headers["content-disposition"]
    assert [r["Keyword"] for r in table] == ["big kw", "what is a roth ira", "small kw"]
    assert [r["Rank"] for r in table] == ["1", "2", "3"]
    roth = table[1]
    assert roth["Verdict"] == "Worth targeting"
    assert roth["Monthly searches"] == "10000" and roth["Volume source"] == "Entered by user"
    assert roth["Top 3 ranking sites"] == "irs.gov; example-finance.com; broker-b.com"
    assert "AI Overview (-52% at #1)" in roth["Features that reduce clicks"]
    assert roth["First recommendation"] == "Write an answer Google can cite"
    assert roth["Analyzed"] == "2026-10-24" and roth["Country"] == "United States"
    assert table[0]["Country"] == "India"


def test_keywords_without_volume_rank_last_with_blank_clicks():
    no_volume = roth_row(volume=None)
    no_volume["volume_source"] = "unknown"
    table = read_csv(client.post("/report", json={"rows": [no_volume, plain_row("big kw", 50000)], "format": "csv"}))
    assert table[1]["Keyword"] == "what is a roth ira"
    assert table[1]["Capturable clicks / month"] == "" and table[1]["Monthly searches"] == ""
    assert table[1]["Volume source"] == "Unknown"


def test_csv_neutralises_spreadsheet_formulas():
    evil = plain_row("=HYPERLINK(\"http://x\")", 1000)
    evil["keyword"] = '=HYPERLINK("http://x")'
    table = read_csv(client.post("/report", json={"rows": [evil], "format": "csv"}))
    assert table[0]["Keyword"] == "'=HYPERLINK(\"http://x\")"


def test_rankings_csv_lists_each_position_and_site():
    res = client.post("/report", json={"rows": [roth_row(), plain_row("big kw", 50000)], "format": "rankings"})
    table = read_csv(res)
    assert 'filename="startly-page-one-' in res.headers["content-disposition"]
    roth = [r for r in table if r["Keyword"] == "what is a roth ira"]
    assert [r["Position"] for r in roth] == [str(i) for i in range(1, 9)]
    assert roth[0]["Site"] == "irs.gov" and int(roth[0]["Clicks / month"]) > int(roth[1]["Clicks / month"])
    assert table[0]["Keyword"] == "big kw"  # ranked like the dashboard


def page_count(pdf: bytes) -> int:
    return pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")


def test_pdf_is_a_full_document_with_contents_and_sections():
    rows = [roth_row(changes={"has_previous": True, "has_changes": True, "previous_fetched_at": "2026-10-21T13:55:23+00:00",
                              "current_fetched_at": "2026-10-24T06:56:20+00:00", "clicks_before": 2060, "clicks_after": 2305,
                              "summary": ["Top ads disappeared.", "Capturable clicks: 2,060 → 2,305 (+12%)."]}),
            plain_row("big kw", 50000)]
    res = client.post("/report", json={"rows": rows, "format": "pdf"})
    assert res.status_code == 200 and res.content.startswith(b"%PDF")
    assert 'filename="startly-report-' in res.headers["content-disposition"]
    # cover, contents, summary, how to read, a page per keyword, method and sources
    assert page_count(res.content) >= 7
    # The PDF outline (bookmarks) lists every section and keyword.
    for title in (b"Summary", b"How to read this report", b"Keyword details", b"what is a roth ira", b"big kw", b"Method and sources"):
        assert title in res.content, title


def test_single_keyword_pdf_skips_contents_and_summary():
    res = client.post("/report", json={"rows": [roth_row()], "format": "pdf"})
    assert res.status_code == 200
    assert page_count(res.content) == 4  # cover, how to read, the keyword, method and sources
    assert b"Summary" not in res.content


def test_pdf_handles_keywords_without_volume_or_organic_results():
    no_volume = roth_row(volume=None)
    no_volume["volume_source"] = "unknown"
    empty = analyze_payload({"keyword": "empty", "keyword_data": {}, "items": [{"type": "ai_overview"}]}, "empty", volume_override=100)
    res = client.post("/report", json={"rows": [no_volume, {**empty, "provider": "serpapi"}], "format": "pdf"})
    assert res.status_code == 200 and page_count(res.content) >= 6


def test_older_rows_without_new_fields_still_export():
    minimal = {"keyword": "legacy", "raw_volume": 1000, "volume_source": "user", "report": None}
    for fmt in ("csv", "rankings", "pdf"):
        assert client.post("/report", json={"rows": [minimal], "format": fmt}).status_code == 200, fmt


def test_empty_export_is_rejected():
    assert client.post("/report", json={"rows": [], "format": "csv"}).status_code == 422


def test_browser_can_read_the_export_file_name():
    res = client.post("/report", headers={"Origin": "http://localhost:3000"}, json={"rows": [roth_row()], "format": "csv"})
    assert "content-disposition" in res.headers.get("access-control-expose-headers", "").lower()
