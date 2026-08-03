---
name: seo-content-opportunity-engine
description: Turn page-level GSC and GA4 performance, keyword data, SEO opportunity tables, and technical-audit evidence into prioritized content work. Use when Codex needs to decide whether to update, create, merge/differentiate, keep, or observe SEO pages; generate evidence-backed page briefs, English US-market title/meta/H1/H2/FAQ/CTA candidates, internal-link suggestions, or a 14/28-day SEO experiment ledger without publishing content or changing a CMS.
---

# SEO Content Opportunity Engine

Use first-party performance data as the decision layer and technical findings as blockers. Generate proposals only; never publish, delete, merge, redirect, or edit a live page.

## Workflow

1. Prefer current outputs from `$seo-gsc-ga4-analyst`:
   - `data/processed/seo_merged_pages_90d.csv`
   - `data/processed/gsc_keywords_90d.csv`
   - `reports/seo_opportunities.csv`
   - optional `data/raw/gsc_90d.csv` for the actual data window.
2. Add `technical_findings.csv` from `$seo-technical-health-auditor` when available.
3. Run:

```bash
python3 <skill-dir>/scripts/build_content_backlog.py \
  --seo-merged-pages /path/data/processed/seo_merged_pages_90d.csv \
  --gsc-keywords /path/data/processed/gsc_keywords_90d.csv \
  --seo-opportunities /path/reports/seo_opportunities.csv \
  --gsc-raw /path/data/raw/gsc_90d.csv \
  --technical-findings /path/technical_findings.csv \
  --site-name "Example" \
  --market US \
  --output-dir ./seo-runs/content
```

4. Read [references/data-contract.md](references/data-contract.md) before changing scoring, decisions, or experiment fields.
5. Review proposed facts, brand claims, product compatibility, prices, shipping, warranties, and installation advice against approved source material before implementation.

## Required Outputs

- `content_backlog.csv`
- `page_briefs/*.md`
- `internal_link_plan.csv`
- `seo_experiment_ledger.csv`
- `content_opportunity_report.md`
- `content_run_manifest.json`

## Decision Rules

- Fix verified P0 technical blockers before content changes.
- Use high-impression/low-CTR, position 8–20, and high-session/low-conversion rules from `$seo-gsc-ga4-analyst`.
- Treat new-page and merge ideas as candidates. Require distinct intent and human approval.
- Keep original English queries unchanged in Chinese reports.
- Do not claim competitor, SERP, backlink, or search-volume evidence unless a named source provides it.
- Do not mark an experiment `running` until an approved change and implementation date are recorded.
