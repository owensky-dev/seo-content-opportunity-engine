# Content opportunity data contract

## Inputs

Required:

- `seo_merged_pages_90d.csv` with `page_url`, GSC metrics, and GA4 page metrics.

Recommended:

- `gsc_keywords_90d.csv`: `page_url,query,clicks,impressions,ctr,position`.
- `seo_opportunities.csv`: existing analyst signals and recommendations.
- raw GSC rows with a `date` column for the actual evidence window.
- `technical_findings.csv` from the technical auditor.

## Decisions

- `fix_technical_first`: verified P0 access/indexing/canonical blocker.
- `update`: existing page has measurable CTR, rank, conversion, or on-page opportunity.
- `create_candidate`: query intent may deserve a distinct page; never treat this as approval to create it.
- `merge_or_differentiate`: the same query has material impressions on multiple pages; inspect intent before consolidation.
- `keep`: current evidence supports preserving the page and measuring it as a control.
- `observe`: evidence is too weak for a change.

## Experiment states

Use `proposed`, `approved`, `running`, `won`, `lost`, `inconclusive`, or `cancelled`. The generator emits only `proposed`.

Implementation date and 14/28-day review dates remain blank until a human-approved change is actually deployed. Baseline values come from the supplied first-party files and must not be invented.

## Safety

Generated titles, descriptions, headings, FAQ themes, CTA concepts, and internal links are drafts. Validate business facts and product claims before implementation. CMS writes, redirects, deletion, merging, and publication require explicit approval.
