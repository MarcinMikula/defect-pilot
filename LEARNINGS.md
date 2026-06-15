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

---

## Sprint 2 — AI Enricher (June 2026)

### 🔍 Technical findings

**Jira Cloud attachments redirect to external CDN (303)**
- `GET /rest/api/3/attachment/content/{id}` returns **303 See Other** — not the file directly.
- Redirect target: `api.media.atlassian.com` with a signed token in the URL.
- Fix: manual two-step download — follow redirect WITHOUT auth headers (external CDN doesn't need them).
- Lesson: always test attachment download separately from metadata parsing. Different code path, different failure modes.

**Screenshots pasted into description = ADF `mediaSingle` nodes**
- Testers frequently drag & drop screenshots directly into the description field (faster than attachment panel).
- These appear as `mediaSingle` → `media` ADF nodes with `attrs.id` pointing to the attachment.
- Same attachment also appears in the `attachment` field — same ID, deduplication needed.
- `_adf_to_text()` now collects these IDs silently while parsing text.

**Multimodal enrichment — text + vision**
- `AnthropicProvider` extended with `complete_with_images()` — base64 images as content blocks.
- `OllamaProvider` text-only for now — vision depends on model (`llava` supports it, `llama3` does not).
- Graceful fallback: if provider doesn't have `complete_with_images`, enricher falls back to text-only with a warning.
- Lesson: don't assume vision support — check at runtime, degrade gracefully.

**Prompt engineering — bilingual PL/EN**
- Defects in Polish projects will have Polish descriptions. AI instructed to respond in the same language as the bug report.
- Section headers defined in both languages (`KROKI REPRODUKCJI / STEPS TO REPRODUCE`) — parser checks both variants.
- "Brak" (PL) and "None" (EN) both filtered out as empty values.

**Ollama — not installed by default**
- Requires separate installation + model download (~2-4GB per model).
- `WinError 10061` = Ollama process not running, not a config issue.
- For first-time users: `ollama serve` + `ollama pull llama3.2` are prerequisites.
- Vision support is model-dependent — document clearly which models support images.

### 🧪 Test results

- 55 unit tests, 55 passed
- DefectEnricher: 21 new tests — parsing, screenshot handling, prompt building
- All AI calls mocked — no real API needed in CI

### 📌 Watch out for

- Attachment CDN tokens are time-limited (signed URLs) — don't cache the redirect URL, always re-request via Jira
- Screenshot MIME type detection: Jira sometimes returns `image/png` even for JPEGs — check extension as fallback
- AI response parsing is section-header based — if AI changes formatting, parser silently returns empty fields. Add validation in Sprint 4.

### 💡 Ideas parked for later

**Additional AI providers — natural extension of pluggable architecture:**

| Provider | Why interesting |
|----------|----------------|
| `gemini` | 1M token context window, native vision, cheaper than Anthropic, free tier in Google AI Studio |
| `openai` | GPT-4o vision, widely adopted in enterprise |

Both = single new file + one line in `provider_factory.py`. Architecture already supports it.

**Provider comparison table** (planned for Sprint 5 README):
quality vs cost vs privacy vs vision support vs speed

---

## Architectural decision — scope boundary (June 2026)

### 🤔 The temptation we resisted

During Sprint 2 we considered expanding defect-pilot toward a full enterprise QA platform:
- Flow library — reusable Playwright step fragments shared across retests
- POM/SOM framework with auto-generated Page Objects
- Self-healing selectors (Shadow DOM, Salesforce LWC)
- Retest scheduler with deployment window awareness
- Multi-provider AI comparison dashboard

This would have made defect-pilot a genuinely powerful but also genuinely unfinishable solo project.

### ✅ Decision: stay focused on v1 scope

**defect-pilot v1 does exactly four things:**
1. Reads Jira defect (done ✅)
2. AI enriches it with technical context (done ✅)
3. Generates a simple flat Playwright retest script (Sprint 3)
4. Updates Jira with enriched data + script (Sprint 4)

No POM. No flow library. No self-healing. No framework.
A flat script that reproduces the bug is already 10x better than nothing.

### 🔮 Where the ambitious stuff goes

The "klocki" (building blocks) approach:
- `qa-automation-framework` — POM/SOM patterns, already in progress
- `PhoenixQA` — self-healing, self-training framework concept, parked
- Future: these projects may be composed into something larger

A finished simple tool beats an unfinished complex one every time.
Especially for a portfolio. Especially for a solo developer + Claude. 😄

---

## Sprint 2 — field session addendum (June 2026)

### 🐛 ADF HTML injection — deeper than expected

**Salesforce ADF injects `<span>` tags into Jira fields**
- Salesforce embeds Aura component markup directly into Jira text fields — even the `summary` (title).
- Example: `<span data-aura-rendered-by="12539:0" class="uiOutputText" data-aura-class="uiOutputText">Mark Status as Complete</span>`
- This happens because Salesforce's Aura framework intercepts copy-paste and injects its own rendering markup.
- Fix: `strip_html()` in `jira_reader.py` using `BeautifulSoup` — strips tags, keeps inner text.
- Commit: `fix: strip HTML tags from Jira fields (Salesforce ADF span injection)`

**⚠️ HTML strip also strips URLs — data loss**
- `<a href="https://...">` links in the description are stripped along with `<span>` tags.
- URL of the affected page (critical for retest!) is silently lost.
- Fix needed: extract `href` attributes from `<a>` tags **before** stripping.
- Pattern: `[a["href"] for a in soup.find_all("a", href=True)]`
- Store as `urls` list in enriched issue dict — pass to AI prompt explicitly.

**RSS export ≠ REST API v3 — again**
- RSS shows HTML-formatted description with `<a href>` visible.
- REST API v3 returns ADF JSON — URLs live in `{"type": "text", "marks": [{"type": "link", "attrs": {"href": "..."}}]}` nodes.
- `_adf_to_text()` must also extract link `href` from mark nodes, not just text content.

---

### 🔗 Issue links — not parsed (bug found in field testing)

**`links: 0` reported despite real issue link in Jira**
- STWA-9 has a "Blocks" relationship with STWA-10 (the requirement Epic).
- REST API v3 returns `issuelinks` array — but parser returned `links: 0`.
- Root cause: `issuelinks` field needs to be explicitly requested in `fields=` param **and** parsed separately from `outwardIssue` / `inwardIssue` keys.
- Fix needed in `jira_reader.py`:

```python
for link in issue.fields.issuelinks:
    if hasattr(link, "outwardIssue"):
        links.append({"key": link.outwardIssue.key, "direction": "outward", "type": link.type.name})
    elif hasattr(link, "inwardIssue"):
        links.append({"key": link.inwardIssue.key, "direction": "inward", "type": link.type.name})
```

**Linked issue = requirement — huge enrichment value**
- STWA-10 (Epic, "Blocks" STWA-9) contains the functional requirement:
  *"uprawniony użytkownik ma mieć możliwość utworzenia, zapisania i zmiany statusów Leada"*
- If enricher fetches linked issues and passes requirement text to AI prompt → much richer context for retest script generation.
- Priority: fetch linked issues of type Epic/Story — pass as `requirement_context` to `DefectEnricher`.

---

### 💬 Selector in comment — gold for Playwright Writer

**Tester left CSS selector in a comment**
- STWA-9, comment: `#\31 2497\:0 > div > div.slds-grid.slds-path__action... > button > span`
- This is a Salesforce LWC dynamically-generated selector — would be nearly impossible to derive from screenshot alone.
- Comments are already fetched (`comments: 1` in output) — but `DefectEnricher` prompt doesn't currently include comment content.
- Fix: include comment text in AI prompt. Selectors mentioned in comments → `ui_elements` in enriched output → Playwright `locator()` calls.
- This is a significant quality boost for Sprint 3 (Playwright Writer).

---

### 🔢 Completeness score parser bug

**Score `10/100` parsed as `101/100`**
- AI responded with `KOMPLETNOŚĆ: 10 / 100 (...)` — parser extracted `101` instead of `10`.
- Likely regex issue: captures `10` then appends `1` from surrounding text, or captures `1` from "1 screenshot" and concatenates.
- Fix: use explicit regex `(\d{1,3})\s*/\s*100` and take only the **first** match, validate range `0–100`.

---

### 🔒 SSL / certifi — Windows Microsoft Store Python

**Python from Microsoft Store doesn't inherit Windows certificate trust chain**
- `curl` (PowerShell) connected fine — Windows trusted the Atlassian cert.
- Python `requests` failed with `CERTIFICATE_VERIFY_FAILED` — because MS Store Python uses its own isolated certstore.
- This is a known issue with `PythonSoftwareFoundation.Python.3.12` from the Store.
- Fix: `pip install pip-system-certs` — bridges Windows CertStore into Python's SSL context, zero code changes.
- Alternative: `pip install --upgrade certifi` if the cert bundle is simply outdated.
- **Lesson:** If it worked before and broke now → suspect certifi bundle rotation or Windows Update touching cert chain. Check Python source (Store vs python.org installer) before debugging code.

---

### 📋 Completeness checklist — proposed standard (Sprint 3 input)

Based on field testing with STWA-9, a defect report is "complete" when it contains:

| Field | Source | Status in STWA-9 |
|-------|--------|-----------------|
| Steps to reproduce | description / AI | ✅ extracted by AI |
| Expected result | description / AI | ✅ extracted |
| Actual result | description / AI | ✅ extracted |
| URL / navigation path | description `<a href>` | ❌ stripped by HTML fix — needs URL extractor |
| Error message | description / screenshot | ✅ AI correctly said "not visible" |
| Screenshot | attachment | ✅ present |
| Requirement reference | title / linked issue | ⚠️ title only — linked issue not fetched |
| CSS/UI selector | comment | ⚠️ present in comment but not passed to AI |
| Environment (browser, OS, role) | environment field / description | ❌ empty |
| Assignee / reporter | Jira fields | ✅ |

**Next step:** `jira_writer.py` module — writes missing fields back to Jira as an "🤖 AI Enrichment" section appended to description (non-destructive, original text preserved).

---

_Next update: after Sprint 3 — Playwright Writer_

---

## Sprint 3 — pre-kickoff notes (June 2026)

### 🧪 Test Data Problem — parked for Sprint 3

**Context:** STWA-9 bug report contains a direct link to a specific Salesforce Lead:
`https://brave-goat-4r7ip-dev-ed.trailblaze.lightning.force.com/lightning/r/Lead/00Qd200000XByc9EAD/view`

A retest script navigating to this hardcoded URL will fail if:
- The Lead was closed, converted, or deleted
- The Lead status was manually changed (bug "fixed" but not via proper flow)
- The environment was refreshed with new data

**This is the #1 reliability problem for business application retest scripts.**
It's not a Playwright problem — it's a test data lifecycle problem.

**Strategies considered for Sprint 3 (v1 = flat script):**

| Strategy | Complexity | Notes |
|----------|-----------|-------|
| **Parametrize via CLI** `--lead-id` | Low ✅ | Tester provides fresh ID before run. Simple, explicit. v1 choice. |
| Fixture setup — create Lead before test | Medium | Script creates Lead via UI/API, uses its ID, deletes after. Brittle for UI-based creation. |
| Query for open Lead | Medium | Playwright + Salesforce API query. Requires API access config. |
| `test_data.json` alongside script | Low | Tester edits JSON before run. Less elegant than CLI but works. |

**Decision for v1:** CLI parametrization — `--lead-id` optional arg.
- If provided: script uses it directly
- If not provided: script uses URL from enriched defect (best-effort, may be stale)
- Script prints a warning if navigating to a hardcoded ID

**Broader lesson:** Any retest script for a CRUD application needs to answer:
*"Where does the test data come from, and who is responsible for its state?"*
This question should be in the AI prompt for Sprint 3 — ask AI to identify
what data the test needs and flag hardcoded IDs as parametrization candidates.

---

_Next update: after Sprint 3 — Playwright Writer_