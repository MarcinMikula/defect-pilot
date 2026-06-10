# 📓 LEARNINGS.md — defect-pilot project diary

> Lessons learned, architectural decisions, dead ends, and "aha" moments.  
> Updated after every sprint. Honest notes — not a changelog.

---

## Sprint 0 — Foundations (June 2025)

### 🏛️ Architectural decisions

**Decision: Pluggable AI provider via config, not interactive prompt**
- _Why:_ Many QA teams work under NDA / data residency constraints. Jira tickets = documentation. Can't send to external APIs without explicit consent. Tester sets `AI_PROVIDER=ollama` in `.env` once, and data never leaves the machine.
- _Alternative considered:_ Interactive CLI prompt at startup — rejected because it breaks automation pipelines and CI/CD usage.

**Decision: SQLite for local defect tracking**
- _Why:_ Zero infrastructure, works offline, easy to inspect, good enough for single-tester or small-team use. Not trying to be a Jira replacement.
- _Alternative considered:_ PostgreSQL — overkill for v1, can be swapped later via SQLAlchemy if needed.

**Decision: Playwright for retest script generation**
- _Why:_ Native Shadow DOM support via `pierce` selectors — critical for Salesforce use case. Also aligns with existing stack in `qa-automation-framework`.
- _Constraint acknowledged:_ Shadow DOM in Salesforce (LWC components) is genuinely hard. Setting the bar high on purpose — good portfolio signal.

**Decision: Start with frontend defects only (v1)**
- _Why:_ API/microservice retest is a different problem domain. Better to do one thing well.  
- _Future:_ Separate project or v2 module for API-level retests.

---

### 🎯 Project positioning

- Targets: AI-powered QA roles, teams using Jira + Salesforce/complex SPAs
- GitHub discoverability: topics set from day 1, README written before first feature
- UAT environment: own Jira Cloud instance + Salesforce Developer Edition (free)
- Synthetic defects for demo — intentional, noted in README

---

### 📌 Things to watch out for

- Jira API rate limits — add retry logic early, don't leave for last sprint
- Playwright script generation quality heavily depends on prompt engineering — expect multiple iterations in Sprint 2/3
- Ollama model quality vs Anthropic will differ — need to test both and document gaps
- Shadow DOM selectors in Salesforce LWC change between SF releases — scripts may need re-generation

---

### 💡 Ideas parked for later

- Web UI / dashboard for non-CLI users
- Slack notification when retest script is ready
- Multi-issue batch processing (`--issues PROJ-123,PROJ-124,PROJ-125`)
- Confidence score on generated retest scripts ("I'm 80% sure this will reproduce the bug")

---

_Next update: after Sprint 2 — AI Enricher_

---

## Sprint 1 — Jira Reader (June 2025)

### 🔍 Technical findings

**Jira REST API v3 returns ADF, not plain text**
- Description field comes back as Atlassian Document Format (ADF) — nested JSON, not a string.
- Had to write `_adf_to_text()` recursive parser. Handles: paragraphs, headings, bullet/ordered lists, hard breaks.
- Lesson: always check the actual API response shape before assuming. RSS export ≠ REST API.

**Project key confirmed: `STWA`**
- Jira instance: `marcin00001a-1758457062887.atlassian.net`
- Board is Scrum-based, sprint field is `customfield_10020`
- Issue type in this project is "Zadanie" (Polish locale) — parser uses `issuetype.name` so locale-agnostic ✅

**No dedicated steps/expected/actual fields**
- Everything lives in free-text `description`
- AI enricher (Sprint 2) will need to extract structure from unstructured text
- This is realistic — 90% of real Jiras look like this

### 🧪 Test results

- 24 unit tests, 24 passed
- Full mock coverage — no real Jira calls needed in CI
- Covered: ADF parsing, field mapping, error handling (401/404/500), attachments, sprint, no-assignee edge case

### 📌 Watch out for

- `customfield_10020` (Sprint) is a list — always take the last element (active sprint)
- Attachment URLs require auth headers to download — relevant for Sprint 2 when we'll process screenshots
- Rate limits: Jira Cloud allows ~100 req/min on free tier — not an issue for single-issue flow, will matter for batch mode

