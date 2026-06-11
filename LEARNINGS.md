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

### ⚠️ Jira configuration variance — critical for adopters

**This is the #1 thing that will break defect-pilot on a new project.**

Every Jira instance is configured differently. Things that vary per project/company:

| Element | This project (STWA) | May look like elsewhere |
|---------|-------------------|------------------------|
| Issue type — Task | "Zadanie" | "Task", "Story", "Ticket" |
| Issue type — Bug | "Błąd" | "Bug", "Defect", "Error", "Problem" |
| Link type | "Blocks" | "Blokuje" (PL), "Blocks", "is blocked by" — **same relationship, different names** |
| Steps to reproduce | Inside free-text `description` | Dedicated custom field (`customfield_XXXXX`) |
| Environment | Standard field (often empty) | Custom field, or inside description |
| Sprint field | `customfield_10020` | May differ on older Jira versions |
| Story points | `customfield_10016` | `customfield_10028` or `story_points` depending on Jira version |

**Design decisions made because of this:**
- `issue_type` stored as raw string — never compared against hardcoded values like `== "Bug"`
- `link_type` stored as raw string — locale/config agnostic
- `description` parsed as free text — AI enricher responsible for extracting structure
- Parser uses defensive `or {}` / `or []` everywhere — missing fields don't crash

**Recommendation for anyone adapting this tool:**
Run `GET /rest/api/3/issue/{YOUR-ISSUE-KEY}` on your Jira first and inspect the raw JSON.
Map your custom fields before configuring. A `field_mapping.yml` config is planned for Sprint 5.

---

### 💡 Idea parked for later — retest scheduler

**Context:** In enterprise environments, deployment windows are fixed (e.g. Mon–Fri 13:00–14:00).
After a deployment window closes, a tester needs to check if any defects moved to "Ready for retest" status — currently done manually by checking email or Jira.

**Proposed feature (Sprint 4 or 5):**
- Configurable scheduler: set time + days in `.env` or `config.yml`
- Agent polls Jira after deployment window: finds issues with status "Ready for retest" / "Do retestu" (configurable — locale variance again!)
- Triggers retest script generation automatically
- Notifies tester (log, file, optional Slack/email)

**Config sketch:**
```yaml
retest_scheduler:
  enabled: true
  check_after: "14:00"          # poll after deployment window closes
  days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
  retest_status: "Ready for retest"   # configurable — locale-dependent!
  timezone: "Europe/Warsaw"
```

**Implementation note:** `APScheduler` or simple `schedule` library + cron-style config.
Status name must be configurable — "Ready for retest", "Do retestu", "Gotowe do retestu" are all the same thing on different projects.

