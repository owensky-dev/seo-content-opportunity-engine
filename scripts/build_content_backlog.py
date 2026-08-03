#!/usr/bin/env python3
"""Build deterministic SEO content tasks from GSC, GA4, and technical evidence."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import statistics
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path


PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "": 9}
STOPWORDS = {
    "a", "an", "and", "are", "at", "by", "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "to", "with", "your",
}
PROBLEM_WORDS = {"how", "what", "why", "guide", "install", "installation", "size", "sizing", "clean", "repair", "cost", "ideas"}
COMPARISON_WORDS = {"vs", "versus", "compare", "comparison", "best", "alternative", "alternatives"}
PURCHASE_WORDS = {"buy", "sale", "price", "discount", "shop", "shipping", "near"}


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso_time(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def read_csv(path: str | None) -> list[dict]:
    if not path:
        return []
    with Path(path).expanduser().resolve().open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def number(value, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", "")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def normalize_url(value: str) -> str:
    parsed = urllib.parse.urlsplit((value or "").strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    host = (parsed.hostname or "").lower()
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), host, path, "", ""))


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def tokens(value: str) -> list[str]:
    values = []
    for token in re.findall(r"[a-z0-9]+", (value or "").lower()):
        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        if len(token) > 1 and token not in STOPWORDS:
            values.append(token)
    return values


def brand_terms(site_name: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", site_name)
    return set(tokens(site_name) + tokens(spaced))


def usable_query(value: str) -> bool:
    lowered = (value or "").lower()
    query_tokens = tokens(lowered)
    return bool(query_tokens) and ".com" not in lowered and "http" not in lowered and "www" not in query_tokens and "com" not in query_tokens


def classify_intent(query: str, site_name: str) -> str:
    items = set(tokens(query))
    brand_tokens = brand_terms(site_name)
    lowered = query.lower()
    if brand_tokens and brand_tokens.intersection(items):
        return "brand"
    if items.intersection(PURCHASE_WORDS) or "near me" in lowered or "free shipping" in lowered:
        return "purchase"
    if items.intersection(COMPARISON_WORDS):
        return "comparison"
    if items.intersection(PROBLEM_WORDS):
        return "problem"
    if items:
        return "product"
    return "informational"


def page_label(url: str) -> str:
    path = urllib.parse.urlsplit(url).path.strip("/")
    if not path:
        return "Home"
    slug = path.split("/")[-1]
    words = re.sub(r"[-_]+", " ", slug).strip()
    return words.title() or "Page"


def safe_slug(value: str) -> str:
    base = "-".join(tokens(urllib.parse.urlsplit(value).path)[-5:]) or "home"
    digest = hashlib.sha1(value.encode()).hexdigest()[:7]
    return f"{base[:70]}-{digest}"


def task_id(decision: str, url: str, query: str = "") -> str:
    return "content-" + hashlib.sha1(f"{decision}|{url}|{query}".encode()).hexdigest()[:12]


def date_window(rows: list[dict]) -> tuple[str, str]:
    dates = sorted({str(row.get("date", "")).strip() for row in rows if re.fullmatch(r"\d{4}-?\d{2}-?\d{2}", str(row.get("date", "")).strip())})
    if not dates:
        return "", ""
    def fmt(value: str) -> str:
        return value if "-" in value else f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return fmt(dates[0]), fmt(dates[-1])


def source_state(path: str | None, rows: list[dict], required: bool = False) -> dict:
    if not path:
        return {"status": "unknown" if required else "not_applicable", "path": "", "rows": 0, "evidence": "not provided"}
    resolved = Path(path).expanduser().resolve()
    return {"status": "normal" if resolved.exists() and rows else "unknown", "path": str(resolved), "rows": len(rows), "evidence": f"rows={len(rows)}"}


def weighted_query_summary(keyword_rows: list[dict], site_name: str, page_url: str = "") -> tuple[str, str, str]:
    clean_rows = [row for row in keyword_rows if usable_query(row.get("query", ""))]
    site_brand_terms = brand_terms(site_name)
    page_tokens = set(tokens(urllib.parse.urlsplit(page_url).path)) - site_brand_terms
    def relevance(row: dict) -> tuple[float, float]:
        query_tokens = set(tokens(row.get("query", ""))) - site_brand_terms
        overlap = len(query_tokens.intersection(page_tokens)) / max(1, len(query_tokens))
        return (number(row.get("impressions")) * (0.5 + 3.0 * overlap), number(row.get("clicks")))
    relevant = [row for row in clean_rows if not page_tokens or (set(tokens(row.get("query", ""))) - site_brand_terms).intersection(page_tokens)]
    if page_tokens:
        non_brand = [row for row in relevant if classify_intent(row.get("query", ""), site_name) != "brand"]
        relevant = non_brand or relevant
    ordered = sorted(relevant or clean_rows, key=relevance, reverse=True)
    top_query = (ordered[0].get("query") or "").strip() if ordered else ""
    weighted = Counter()
    for row in ordered[:50]:
        weight = max(1.0, number(row.get("impressions")))
        for token in tokens(row.get("query", "")):
            weighted[token] += weight
    theme = " ".join(token for token, _ in weighted.most_common(4)) or " ".join(tokens(top_query)[:4])
    intent = classify_intent(top_query, site_name) if top_query else "unknown"
    return top_query, theme, intent


def title_case_topic(value: str, fallback: str) -> str:
    topic = " ".join(tokens(value)[:8]) or fallback
    return " ".join(word.upper() if word in {"led", "usa"} else word.capitalize() for word in topic.split())


def brief_candidates(topic: str, site_name: str, intent: str) -> dict:
    if intent in {"purchase", "product"}:
        third = f"Shop {topic} for Your Space | {site_name}"
    else:
        third = f"{topic}: What to Know Before You Choose | {site_name}"
    return {
        "titles": [
            f"{topic} | {site_name}",
            f"{topic}: Sizes, Features & Buying Guide | {site_name}",
            third,
        ],
        "metas": [
            f"Explore {topic.lower()} options, compare sizes and features, and find the right fit for your space at {site_name}.",
            f"Use this {topic.lower()} guide to compare configurations, installation considerations, and common questions before choosing.",
            f"Review {topic.lower()} details, dimensions, and practical buying considerations in one place.",
        ],
        "h1": topic,
    }


def section_plan(url: str, topic: str, intent: str) -> list[str]:
    path = urllib.parse.urlsplit(url).path
    if path.startswith("/products/"):
        return [f"{topic} key features", "Dimensions and compatibility", "Installation considerations", "Care and maintenance", "Frequently asked questions"]
    if path.startswith("/blogs/") or intent in {"problem", "informational"}:
        return ["Quick answer", "How to choose or complete the task", "Common mistakes", "Product or collection next steps", "Frequently asked questions"]
    return [f"How to choose {topic.lower()}", "Sizes and configurations", "Installation considerations", "Compare available options", "Frequently asked questions"]


def acceptance_metric(signals: list[str]) -> str:
    metrics = []
    if "high_impressions_low_ctr" in signals:
        metrics.append("14/28-day CTR and clicks versus baseline")
    if "position_8_20" in signals or "content_gap_candidate" in signals:
        metrics.append("28-day impressions, clicks, and average position")
    if "high_sessions_low_conversion" in signals:
        metrics.append("organic sessions to conversion rate and funnel events")
    if any(signal.startswith("technical_") for signal in signals):
        metrics.append("technical check passes on rerun")
    return "; ".join(metrics) or "28-day clicks, impressions, and no material conversion regression"


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in columns} for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seo-merged-pages", required=True)
    parser.add_argument("--gsc-keywords")
    parser.add_argument("--seo-opportunities")
    parser.add_argument("--gsc-raw")
    parser.add_argument("--technical-findings")
    parser.add_argument("--site-name", default="Brand")
    parser.add_argument("--market", default="US")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-page-tasks", type=int, default=15)
    parser.add_argument("--max-new-page-candidates", type=int, default=5)
    args = parser.parse_args()

    now = utc_now()
    observed_at = iso_time(now)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir).expanduser().resolve()
    briefs_dir = output_dir / "page_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    for prior_brief in briefs_dir.glob("*.md"):
        prior_brief.unlink()

    merged_rows = read_csv(args.seo_merged_pages)
    keyword_rows = read_csv(args.gsc_keywords)
    opportunity_rows = read_csv(args.seo_opportunities)
    raw_gsc_rows = read_csv(args.gsc_raw)
    technical_rows = read_csv(args.technical_findings)
    if not merged_rows:
        raise SystemExit("seo_merged_pages input is empty or missing")

    normalized_pages = []
    for row in merged_rows:
        url = normalize_url(row.get("page_url") or row.get("page") or row.get("url") or "")
        if not url:
            continue
        normalized_pages.append({
            **row,
            "url": url,
            "clicks_num": number(row.get("clicks")),
            "impressions_num": number(row.get("impressions")),
            "ctr_num": number(row.get("ctr")),
            "position_num": number(row.get("position")),
            "sessions_num": number(row.get("sessions")),
            "conversions_num": number(row.get("conversions")),
            "revenue_num": number(row.get("totalRevenue", row.get("revenue"))),
            "conversion_rate_num": number(row.get("conversion_rate")),
        })
    if not normalized_pages:
        raise SystemExit("seo_merged_pages has no valid absolute page URLs")

    keywords_by_page: dict[str, list[dict]] = defaultdict(list)
    query_pages: dict[str, list[dict]] = defaultdict(list)
    for row in keyword_rows:
        url = normalize_url(row.get("page_url") or row.get("page") or "")
        query = (row.get("query") or "").strip()
        if url and query:
            keywords_by_page[url].append(row)
            query_pages[query.lower()].append({**row, "url": url})

    opportunities_by_page: dict[str, list[dict]] = defaultdict(list)
    for row in opportunity_rows:
        url = normalize_url(row.get("page") or row.get("page_url") or "")
        if url:
            opportunities_by_page[url].append(row)

    technical_by_page: dict[str, list[dict]] = defaultdict(list)
    for row in technical_rows:
        url = normalize_url(row.get("url", ""))
        if url and row.get("status") in {"abnormal", "unknown"}:
            technical_by_page[url].append(row)

    impressions_p65 = max(20.0, percentile([row["impressions_num"] for row in normalized_pages], 0.65))
    sessions_p65 = max(10.0, percentile([row["sessions_num"] for row in normalized_pages], 0.65))
    median_impressions = max(20.0, statistics.median([row["impressions_num"] for row in normalized_pages]))
    total_impressions = sum(row["impressions_num"] for row in normalized_pages)
    total_clicks = sum(row["clicks_num"] for row in normalized_pages)
    site_ctr = total_clicks / total_impressions if total_impressions else 0.0
    total_sessions = sum(row["sessions_num"] for row in normalized_pages)
    total_conversions = sum(row["conversions_num"] for row in normalized_pages)
    site_conversion_rate = total_conversions / total_sessions if total_sessions else 0.0
    max_impressions = max(row["impressions_num"] for row in normalized_pages)
    max_sessions = max(row["sessions_num"] for row in normalized_pages)

    page_tasks = []
    for page in normalized_pages:
        url = page["url"]
        top_query, theme, intent = weighted_query_summary(keywords_by_page[url], args.site_name, url)
        technical = technical_by_page[url]
        p0_technical = [row for row in technical if row.get("status") == "abnormal" and row.get("priority") == "P0"]
        p1_technical = [row for row in technical if row.get("status") == "abnormal" and row.get("priority") == "P1"]
        unknown_technical = [row for row in technical if row.get("status") == "unknown"]
        signals = []
        if page["impressions_num"] >= impressions_p65 and site_ctr and page["ctr_num"] < site_ctr * 0.7:
            signals.append("high_impressions_low_ctr")
        if page["impressions_num"] >= median_impressions and 8 <= page["position_num"] <= 20:
            signals.append("position_8_20")
        if page["sessions_num"] >= sessions_p65 and site_conversion_rate and page["conversion_rate_num"] < site_conversion_rate * 0.5:
            signals.append("high_sessions_low_conversion")
        if p0_technical:
            signals.append("technical_p0")
        elif p1_technical:
            signals.append("technical_p1")
        if unknown_technical:
            signals.append("technical_unknown")
        for item in opportunities_by_page[url]:
            kind = (item.get("type") or "").strip()
            if kind:
                signals.append("analyst:" + kind)

        path = urllib.parse.urlsplit(url).path
        excluded_page = path.startswith("/policies/") or path in {"/pages/contact", "/search"}
        if p0_technical:
            decision, priority = "fix_technical_first", "P0"
        elif excluded_page:
            decision, priority = "observe", "P3"
        elif any(signal in signals for signal in ["high_impressions_low_ctr", "position_8_20", "high_sessions_low_conversion"]):
            decision, priority = "update", "P1"
        elif p1_technical:
            decision, priority = "update", "P1"
        elif page["clicks_num"] > 0 and (not site_ctr or page["ctr_num"] >= site_ctr) and (not site_conversion_rate or page["conversion_rate_num"] >= site_conversion_rate):
            decision, priority = "keep", "P3"
        else:
            decision, priority = "observe", "P3"

        score = 0.0
        score += 20 if "high_impressions_low_ctr" in signals else 0
        score += 15 if "position_8_20" in signals else 0
        score += 15 if "high_sessions_low_conversion" in signals else 0
        score += 50 if p0_technical else 25 if p1_technical else 0
        score += 35.0 * math.log1p(page["impressions_num"]) / max(1.0, math.log1p(max_impressions))
        score += 15.0 * math.log1p(page["sessions_num"]) / max(1.0, math.log1p(max_sessions))
        score = round(min(score, 100.0), 2)
        topic = title_case_topic(top_query or theme, page_label(url))
        current_task_id = task_id(decision, url)
        brief_path = f"page_briefs/{safe_slug(url)}-{current_task_id[-6:]}.md"
        tech_evidence = " | ".join(f"{row.get('check')}={row.get('evidence')}" for row in technical[:5])
        action = {
            "fix_technical_first": "Resolve the verified P0 technical blocker, rerun the audit, then reconsider content work.",
            "update": "Review title/meta/H1, expand intent-matched sections and FAQ themes, strengthen contextual internal links, and align CTA with page intent.",
            "keep": "Preserve the current page as a control; monitor 14/28-day search and conversion metrics.",
            "observe": "Do not change yet; wait for stronger query/page evidence or a longer data window.",
        }[decision]
        page_tasks.append({
            "task_id": current_task_id,
            "priority": priority,
            "decision": decision,
            "approval_required": "true",
            "url": url,
            "source_page": url,
            "target_query": top_query,
            "query_intent": intent,
            "theme": theme,
            "signals": "; ".join(dict.fromkeys(signals)),
            "priority_score": score,
            "clicks": page["clicks_num"],
            "impressions": page["impressions_num"],
            "ctr": page["ctr_num"],
            "position": page["position_num"],
            "sessions": page["sessions_num"],
            "conversions": page["conversions_num"],
            "revenue": page["revenue_num"],
            "technical_evidence": tech_evidence,
            "recommended_action": action,
            "acceptance_metric": acceptance_metric(signals),
            "brief_path": brief_path,
            "status": "proposed",
            "topic": topic,
        })

    page_tasks.sort(key=lambda row: (PRIORITY_RANK[row["priority"]], -row["priority_score"], -row["impressions"]))
    selected_tasks = [row for row in page_tasks if row["decision"] not in {"observe", "keep"}][: args.max_page_tasks]
    controls = [row for row in page_tasks if row["decision"] == "keep"][:2]
    observations = [row for row in page_tasks if row["decision"] == "observe"][:2]
    backlog = selected_tasks + controls + observations

    # Conservative new-page candidates: strong query, weak ranking, and poor query/path overlap.
    proposed_queries = set()
    proposed_query_token_sets: list[set[str]] = []
    high_query_threshold = max(100.0, percentile([number(row.get("impressions")) for row in keyword_rows if usable_query(row.get("query", ""))], 0.9)) if keyword_rows else 100.0
    existing_paths = {page["url"]: set(tokens(urllib.parse.urlsplit(page["url"]).path)) for page in normalized_pages}
    new_candidates = []
    for row in sorted(keyword_rows, key=lambda item: number(item.get("impressions")), reverse=True):
        query = (row.get("query") or "").strip()
        query_key = query.lower()
        source_url = normalize_url(row.get("page_url") or row.get("page") or "")
        impressions = number(row.get("impressions"))
        position = number(row.get("position"))
        query_tokens = set(tokens(query))
        overlap = len(query_tokens.intersection(existing_paths.get(source_url, set()))) / max(1, len(query_tokens))
        near_duplicate = any(len(query_tokens.intersection(prior)) / max(1, len(query_tokens.union(prior))) >= 0.5 for prior in proposed_query_token_sets)
        if not usable_query(query) or query_key in proposed_queries or near_duplicate or impressions < high_query_threshold or position <= 12 or overlap >= 0.25:
            continue
        intent = classify_intent(query, args.site_name)
        topic = title_case_topic(query, "New SEO Page")
        slug = "-".join(tokens(query)[:8])[:70] or "seo-page"
        proposed_path = f"/blogs/news/{slug}" if intent in {"problem", "informational", "comparison"} else f"/collections/{slug}"
        candidate_url = urllib.parse.urljoin(source_url or normalized_pages[0]["url"], proposed_path)
        signals = ["content_gap_candidate"]
        current_task_id = task_id("create_candidate", candidate_url, query)
        brief_path = f"page_briefs/{safe_slug(candidate_url)}-{current_task_id[-6:]}.md"
        new_candidates.append({
            "task_id": current_task_id,
            "priority": "P2",
            "decision": "create_candidate",
            "approval_required": "true",
            "url": candidate_url,
            "source_page": source_url,
            "target_query": query,
            "query_intent": intent,
            "theme": " ".join(tokens(query)[:5]),
            "signals": "; ".join(signals),
            "priority_score": round(min(80.0, 30 + math.log1p(impressions) * 5), 2),
            "clicks": number(row.get("clicks")),
            "impressions": impressions,
            "ctr": number(row.get("ctr")),
            "position": position,
            "sessions": 0,
            "conversions": 0,
            "revenue": 0,
            "technical_evidence": "",
            "recommended_action": "Validate distinct intent and business fit; create only after confirming no current page can satisfy the query.",
            "acceptance_metric": acceptance_metric(signals),
            "brief_path": brief_path,
            "status": "proposed",
            "topic": topic,
        })
        proposed_queries.add(query_key)
        proposed_query_token_sets.append(query_tokens)
        if len(new_candidates) >= args.max_new_page_candidates:
            break
    backlog.extend(new_candidates)

    # Cannibalization candidates require material impressions on at least two pages.
    merge_candidates = []
    for query, rows in query_pages.items():
        if classify_intent(query, args.site_name) == "brand":
            continue
        material = [row for row in rows if number(row.get("impressions")) >= max(5, high_query_threshold * 0.25)]
        urls = sorted({row["url"] for row in material})
        if len(urls) < 2:
            continue
        winner = max(material, key=lambda row: (number(row.get("clicks")), number(row.get("impressions"))))
        current_task_id = task_id("merge_or_differentiate", winner["url"], query)
        merge_candidates.append({
            "task_id": current_task_id,
            "priority": "P2",
            "decision": "merge_or_differentiate",
            "approval_required": "true",
            "url": winner["url"],
            "source_page": "; ".join(urls),
            "target_query": material[0].get("query", query),
            "query_intent": classify_intent(query, args.site_name),
            "theme": " ".join(tokens(query)[:5]),
            "signals": "query_page_overlap",
            "priority_score": round(min(75.0, 25 + math.log1p(sum(number(row.get('impressions')) for row in material)) * 5), 2),
            "clicks": sum(number(row.get("clicks")) for row in material),
            "impressions": sum(number(row.get("impressions")) for row in material),
            "ctr": 0,
            "position": number(winner.get("position")),
            "sessions": 0,
            "conversions": 0,
            "revenue": 0,
            "technical_evidence": "",
            "recommended_action": "Inspect SERP intent and page roles; differentiate targeting or propose a reviewed consolidation. Do not redirect or delete automatically.",
            "acceptance_metric": "28-day query clicks, impressions, average position, and page distribution",
            "brief_path": f"page_briefs/{safe_slug(winner['url'])}-overlap-{current_task_id[-6:]}.md",
            "status": "proposed",
            "topic": title_case_topic(query, page_label(winner["url"])),
        })
    merge_candidates.sort(key=lambda row: -row["priority_score"])
    backlog.extend(merge_candidates[:3])
    backlog.sort(key=lambda row: (PRIORITY_RANK[row["priority"]], -row["priority_score"], row["url"]))

    internal_links = []
    page_context = {}
    for page in normalized_pages:
        _, theme, _ = weighted_query_summary(keywords_by_page[page["url"]], args.site_name, page["url"])
        page_context[page["url"]] = set(tokens(theme) + tokens(urllib.parse.urlsplit(page["url"]).path))
    for task in backlog:
        if task["decision"] in {"observe", "keep", "fix_technical_first"}:
            continue
        target_tokens = set(tokens(task["target_query"] or task["theme"] or task["url"]))
        candidates = []
        for source, source_tokens in page_context.items():
            if source == task["url"]:
                continue
            similarity = len(target_tokens.intersection(source_tokens)) / max(1, len(target_tokens.union(source_tokens)))
            if similarity > 0:
                candidates.append((similarity, source))
        if not candidates:
            homepage = next((page["url"] for page in normalized_pages if urllib.parse.urlsplit(page["url"]).path == "/"), "")
            if homepage and homepage != task["url"]:
                candidates = [(0.0, homepage)]
        for similarity, source in sorted(candidates, reverse=True)[:2]:
            internal_links.append({
                "link_id": "link-" + hashlib.sha1(f"{source}|{task['url']}".encode()).hexdigest()[:12],
                "priority": task["priority"],
                "source_url": source,
                "target_url": task["url"],
                "anchor_text": task["topic"],
                "placement": "Relevant body copy or buying-guide module",
                "evidence": f"shared_theme_similarity={similarity:.3f}; target_query={task['target_query']}",
                "approval_required": "true",
                "status": "proposed",
            })

    baseline_start, baseline_end = date_window(raw_gsc_rows)
    experiment_rows = []
    for task in backlog:
        if task["decision"] in {"observe", "keep"}:
            continue
        field = "technical_fix" if task["decision"] == "fix_technical_first" else "title_meta_content_internal_links"
        experiment_rows.append({
            "experiment_id": "exp-" + task["task_id"].split("-")[-1],
            "url": task["url"],
            "decision": task["decision"],
            "field": field,
            "hypothesis": task["recommended_action"],
            "baseline_start": baseline_start,
            "baseline_end": baseline_end,
            "baseline_clicks": task["clicks"],
            "baseline_impressions": task["impressions"],
            "baseline_ctr": task["ctr"],
            "baseline_position": task["position"],
            "baseline_sessions": task["sessions"],
            "baseline_conversions": task["conversions"],
            "implementation_date": "",
            "review_14d_date": "",
            "review_28d_date": "",
            "acceptance_metric": task["acceptance_metric"],
            "approval_required": "true",
            "status": "proposed",
        })

    links_by_target: dict[str, list[dict]] = defaultdict(list)
    for link in internal_links:
        links_by_target[link["target_url"]].append(link)
    for task in backlog:
        candidates = brief_candidates(task["topic"], args.site_name, task["query_intent"])
        sections = section_plan(task["url"], task["topic"], task["query_intent"])
        brief_lines = [
            f"# {task['topic']} 页面 Brief",
            "",
            f"- 决策：{task['decision']}（{task['priority']}）",
            f"- URL：{task['url']}",
            f"- 目标查询：`{task['target_query'] or '未形成稳定查询证据'}`",
            f"- 意图：{task['query_intent']}；市场：{args.market}",
            f"- 信号：{task['signals'] or '证据不足，观察项'}",
            f"- 基线：clicks={task['clicks']}, impressions={task['impressions']}, CTR={task['ctr']:.4f}, position={task['position']:.2f}, sessions={task['sessions']}, conversions={task['conversions']}",
            "",
            "## 技术前置条件",
            "",
            task["technical_evidence"] or "未发现已提供技术证据中的阻断项；若技术输入缺失，应视为未知。",
            "",
            "## Title 候选（英文草稿）",
            "",
        ]
        brief_lines.extend(f"- {value}" for value in candidates["titles"])
        brief_lines.extend(["", "## Meta Description 候选（英文草稿）", ""])
        brief_lines.extend(f"- {value}" for value in candidates["metas"])
        brief_lines.extend(["", "## 页面结构", "", f"- H1: {candidates['h1']}"])
        brief_lines.extend(f"- H2: {value}" for value in sections)
        brief_lines.extend([
            "",
            "## FAQ 主题（需用真实产品与客服证据回答）",
            "",
            f"- How do I choose the right {task['topic'].lower()}?",
            f"- What dimensions or compatibility details matter for {task['topic'].lower()}?",
            f"- What should I know about installation and care?",
            "",
            "## CTA 方向",
            "",
            "- Compare available options",
            "- Review dimensions and compatibility",
            "- Continue to the relevant product or collection",
            "",
            "## 内链建议",
            "",
        ])
        if links_by_target[task["url"]]:
            for link in links_by_target[task["url"]]:
                brief_lines.append(f"- {link['source_url']} → {link['target_url']}；锚文本：{link['anchor_text']}")
        else:
            brief_lines.append("- 当前输入未形成可靠的来源页建议，需人工补充。")
        brief_lines.extend([
            "",
            "## 审批与复测",
            "",
            f"- 验收指标：{task['acceptance_metric']}",
            "- 当前状态：proposed；未发布、未修改 CMS。",
            "- 所有价格、库存、配送、保修、安装与兼容性事实必须复核。",
            "",
        ])
        (output_dir / task["brief_path"]).write_text("\n".join(brief_lines), encoding="utf-8")

    backlog_columns = ["task_id", "priority", "decision", "approval_required", "url", "source_page", "target_query", "query_intent", "theme", "signals", "priority_score", "clicks", "impressions", "ctr", "position", "sessions", "conversions", "revenue", "technical_evidence", "recommended_action", "acceptance_metric", "brief_path", "status"]
    link_columns = ["link_id", "priority", "source_url", "target_url", "anchor_text", "placement", "evidence", "approval_required", "status"]
    experiment_columns = ["experiment_id", "url", "decision", "field", "hypothesis", "baseline_start", "baseline_end", "baseline_clicks", "baseline_impressions", "baseline_ctr", "baseline_position", "baseline_sessions", "baseline_conversions", "implementation_date", "review_14d_date", "review_28d_date", "acceptance_metric", "approval_required", "status"]
    write_csv(output_dir / "content_backlog.csv", backlog, backlog_columns)
    write_csv(output_dir / "internal_link_plan.csv", internal_links, link_columns)
    write_csv(output_dir / "seo_experiment_ledger.csv", experiment_rows, experiment_columns)

    sources = {
        "seo_merged_pages": source_state(args.seo_merged_pages, merged_rows, required=True),
        "gsc_keywords": source_state(args.gsc_keywords, keyword_rows),
        "seo_opportunities": source_state(args.seo_opportunities, opportunity_rows),
        "gsc_raw": source_state(args.gsc_raw, raw_gsc_rows),
        "technical_findings": source_state(args.technical_findings, technical_rows),
    }
    if technical_rows:
        unknown_count = sum(row.get("status") == "unknown" for row in technical_rows)
        unknown_ratio = unknown_count / len(technical_rows)
        if unknown_ratio > 0.5:
            sources["technical_findings"]["status"] = "unknown"
            sources["technical_findings"]["evidence"] = f"rows={len(technical_rows)}; unknown_ratio={unknown_ratio:.1%}"
    degraded = any(source["status"] == "unknown" for source in sources.values())
    manifest = {
        "schema_version": "1.0",
        "run_id": run_id,
        "generated_at": observed_at,
        "mode": "draft-only-readonly",
        "status": "degraded" if degraded else "complete",
        "site_name": args.site_name,
        "market": args.market,
        "data_window": {"start": baseline_start, "end": baseline_end},
        "thresholds": {
            "impressions_p65": impressions_p65,
            "sessions_p65": sessions_p65,
            "site_ctr": site_ctr,
            "site_conversion_rate": site_conversion_rate,
        },
        "sources": sources,
        "counts": {
            "input_pages": len(normalized_pages),
            "backlog_tasks": len(backlog),
            "page_briefs": len(backlog),
            "internal_links": len(internal_links),
            "experiments": len(experiment_rows),
        },
        "outputs": {
            "content_backlog": str(output_dir / "content_backlog.csv"),
            "page_briefs": str(briefs_dir),
            "internal_link_plan": str(output_dir / "internal_link_plan.csv"),
            "experiment_ledger": str(output_dir / "seo_experiment_ledger.csv"),
            "report": str(output_dir / "content_opportunity_report.md"),
            "manifest": str(output_dir / "content_run_manifest.json"),
        },
    }
    report_lines = [
        f"# {args.site_name} SEO 内容机会",
        "",
        f"- 运行时间：{observed_at}",
        f"- 状态：{manifest['status']}；数据窗口：{baseline_start or '未知'} 至 {baseline_end or '未知'}",
        f"- 任务：{len(backlog)}；Brief：{len(backlog)}；内链建议：{len(internal_links)}；实验：{len(experiment_rows)}",
        "- 边界：所有内容均为草稿，未写入或发布到网站。",
        "",
        "## 优先任务",
        "",
        "| 优先级 | 决策 | URL | 查询 | 信号 | 分数 |",
        "|---|---|---|---|---|---:|",
    ]
    for task in backlog[:20]:
        report_lines.append(f"| {task['priority']} | {task['decision']} | {task['url']} | {task['target_query'].replace('|', '/')} | {task['signals'].replace('|', '/')} | {task['priority_score']:.2f} |")
    report_lines.extend(["", "## 数据边界", ""])
    for name, source in sources.items():
        report_lines.append(f"- {name}: {source['status']} — {source['evidence']}")
    report_lines.extend(["", "新建、合并、删除、301、Canonical、noindex 与 CMS 发布均需人工审批。", ""])
    (output_dir / "content_opportunity_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    (output_dir / "content_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "run_id": run_id, "tasks": len(backlog), "briefs": len(backlog), "output_dir": str(output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
