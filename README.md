# SEO 内容机会引擎 Skill

[虎皮叔叔 · hupishushu.com](https://hupishushu.com/) · [项目介绍](https://hupishushu.com/projects/seo-content-opportunity-engine/) · [中文使用指南](https://hupishushu.com/skills/seo-content-opportunity-engine/)

`seo-content-opportunity-engine` 把 GSC、GA4 和技术巡检结果转成页面级内容任务。它帮助你判断一个页面应该更新、新建、合并区分、保留还是继续观察，并输出页面 Brief、内链建议和 14/28 天实验台账。

它只生成建议和草稿，不会发布页面。

## 能解决什么问题

- 找出高曝光低 CTR、排名 8—20、自然流量高但转化低的页面；
- 识别查询词与页面意图不匹配；
- 生成 Title、Meta、H1/H2、FAQ、CTA 的候选方向；
- 推荐内链来源页、目标页和锚文本；
- 给每项改动记录假设、审批状态和 14/28 天复测指标；
- 遇到 P0 技术阻断时，优先修技术问题而不是继续堆内容。

## 安装

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo owensky-dev/seo-content-opportunity-engine \
  --path . \
  --name seo-content-opportunity-engine
```

## 使用前准备

推荐先使用：

- `seo-gsc-ga4-analyst` 生成页面、关键词和机会表；
- `seo-technical-health-auditor` 生成技术巡检结果。

然后在 Codex 中说：

> 使用 `$seo-content-opportunity-engine` 读取我的 GSC/GA4 分析目录和技术巡检目录，生成本周最值得处理的页面任务、页面 Brief、内链计划和实验台账。不要发布内容。

## 命令行示例

```bash
python3 ~/.codex/skills/seo-content-opportunity-engine/scripts/build_content_backlog.py \
  --seo-merged-pages ./analytics/data/processed/seo_merged_pages_90d.csv \
  --gsc-keywords ./analytics/data/processed/gsc_keywords_90d.csv \
  --seo-opportunities ./analytics/reports/seo_opportunities.csv \
  --gsc-raw ./analytics/data/raw/gsc_90d.csv \
  --technical-findings ./technical/technical_findings.csv \
  --site-name "Example" \
  --market US \
  --output-dir ./seo-runs/content
```

## 主要产物

- `content_backlog.csv`：页面任务与优先级；
- `page_briefs/*.md`：页面级修改 Brief；
- `internal_link_plan.csv`：内链建议；
- `seo_experiment_ledger.csv`：实验与 14/28 天复测记录；
- `content_opportunity_report.md`：中文汇总报告；
- `content_run_manifest.json`：数据来源与运行状态。

## 决策边界

- GSC/GA4 第一方数据优先；
- 技术来源缺失时明确标为 unknown；
- 新建、合并和删除页面只作为候选；
- 未经人工批准，不修改 CMS、Title、Meta、正文、Schema 或重定向；
- 不伪造竞品、SERP、外链或搜索量证据；
- 价格、库存、尺寸、配送和保修等事实必须再次核对。

## 公众号

如果你正在搭建独立站 SEO、内容增长和 AI 工作流，欢迎扫码，或在微信搜索 **「虎皮叔叔聊跨境独立站」**，关注虎皮叔叔的公众号。这里会围绕 **独立站增长与 AI 营销**，持续更新真实案例、工具拆解和自动化实践。

![公众号二维码](assets/wechat-qr.png)

## 许可证

MIT License
