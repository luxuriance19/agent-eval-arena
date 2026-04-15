# The Pragmatic Engineer - Blog Summary

> Source: https://blog.pragmaticengineer.com/
> Scraped: 2026-04-15

---

## 10 Most Recent Articles

| # | Title | Date | Preview |
|---|-------|------|---------|
| 1 | The Pulse: is GitHub still best for AI-native development? | 2026-04-03 | Availability has dropped to one nine (~90%), partly due to not being able to handle increased traffic from AI coding agents. |
| 2 | Is the FDE role becoming less desirable? | 2026-03-27 | Job postings for Forward Deployed Engineers (FDEs) have surged, but many professionals don't want the role because it's more like solutions engineering. |
| 3 | The Pulse: Cloudflare rewrites Next.js as AI rewrites commercial open source | 2026-03-05 | An engineer at Cloudflare rewrote most of Vercel's Next.js in one week with AI agents. It looks like a sign of how AI will disrupt existing moats. |
| 4 | I replaced a $120/year micro-SaaS in 20 minutes with LLM-generated code | 2026-01-29 | Using an LLM, managed to rewrite all the functionality of a stagnant SaaS in 20 minutes. |
| 5 | The grief when AI writes most of the code | — | — |
| 6 | The Pulse: Cloudflare's latest outage proves dangers of global configuration changes (again) | — | — |
| 7 | The Pulse: Could a 5-day RTO be around the corner for Big Tech? | — | — |
| 8 | Downdetector and the real cost of no upstream dependencies | — | — |
| 9 | A startup in Mongolia translated my book | — | — |
| 10 | The Pulse: Cloudflare takes down half the internet – but shares a great postmortem | — | — |

---

## Deep Dive: Top 3 Articles

### 1. The Pulse: is GitHub still best for AI-native development?

- **Date**: 2026-04-03
- **Word Count**: ~1,272 words
- **Estimated Reading Time**: ~5 minutes
- **Topics**: GitHub reliability, AI agents and infrastructure load, alternative platforms (Pierre Computer / Code.storage), GitHub Copilot, AI-native development

**Opening**:

> We're used to highly reliable systems which target four-nines of availability (99.99%, meaning about 52 minutes of downtime per year), and for it to be embarrassing to barely hit three nines (around 9 hours of downtime per year.) And yet, in the past month, GitHub's reliability is down to one nine! Here's data from the third-party, "missing GitHub status page", which was built after GitHub stopped updating its own status page due to terrible availability.

---

### 2. Is the FDE role becoming less desirable?

- **Date**: 2026-03-27
- **Word Count**: ~521 words
- **Estimated Reading Time**: ~2 minutes
- **Topics**: Forward Deployed Engineer (FDE) role, software engineering career trends, tech hiring market, sales engineering, job market dynamics

**Opening**:

> An interesting trend highlighted by The Wall Street Journal: companies want to hire for FDE roles, but devs are just not that interested: "Job postings on Indeed grew more than 10-fold in 2025 compared with 2024. The number of public company transcripts mentioning the role jumped to 50 from eight over the same period, according to data from AlphaSense. The only problem? Few engineers want the job, which has historically been seen as demanding, undesirable, and less prestigious than product-focused engineering."

---

### 3. The Pulse: Cloudflare rewrites Next.js as AI rewrites commercial open source

- **Date**: 2026-03-05
- **Word Count**: ~3,427 words
- **Estimated Reading Time**: ~14 minutes
- **Topics**: AI-powered code rewriting, commercial open source business models, Cloudflare vs Vercel, Next.js / vinext, open source moats in the AI era

**Opening**:

> This issue is the entire The Pulse issue from the past week, which paying subscribers received seven days ago. This piece generated quite a few comments across subscribers, and so I'm sharing it more broadly, especially as it raises questions on what is defensible and what is not with open source. Today's issue of The Pulse focuses on a single event because it's a significant one with major potential ripple effects. On Tuesday, Cloudflare shocked the dev world by announcing that they have rewritten Next.js in just one week, with a single developer who used only $1,100 in tokens.

---

## Common Themes

Across the 10 most recent articles (and especially the top 3), several recurring themes emerge:

### 1. AI is Reshaping Software Development at Every Level

The dominant thread across these articles is AI's accelerating impact on software engineering. From GitHub struggling with AI agent traffic (#1), to a single developer using AI to rewrite an entire framework in a week (#3), to replacing paid SaaS with LLM-generated code (#4), to the emotional toll of AI writing most code (#5) — AI is reshaping how software is built, who builds it, and what tools survive.

### 2. Infrastructure Reliability Under AI-Era Pressure

GitHub's availability dropping to ~90% due to AI coding agent traffic reveals a systemic challenge: existing infrastructure wasn't designed for the load that AI-native workflows generate. Cloudflare outages (#6, #10) further reinforce that even the most critical infrastructure providers face reliability challenges as the ecosystem evolves rapidly.

### 3. Disruption of Existing Business Moats

Cloudflare's one-week rewrite of Next.js using AI challenges the assumption that commercial open source projects have durable moats. If a competitor can replicate years of engineering effort in days with AI assistance, the defensibility of open source-based business models comes into question.

### 4. Evolving Engineering Roles and Career Landscape

The FDE article highlights a widening gap between what companies want to hire for and what engineers want to do. Traditional role boundaries are blurring, and the profession is grappling with questions of prestige, autonomy, and how AI changes the daily work of an engineer.

### 5. Developer Tooling and Platform Competition

Multiple articles touch on the competition among developer platforms (GitHub vs. alternatives, Vercel vs. Cloudflare, SaaS vs. self-built). The moats that once protected developer tools — ecosystem lock-in, years of accumulated features — are being eroded by AI's ability to rapidly replicate functionality.
