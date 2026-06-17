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
3. Generates a simple flat Playwright retest script (done ✅)
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
- Fix: extract `href` attributes from `<a>` tags **before** stripping.
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
- Fix: implemented in `jira_reader.py` — now fetches full linked issue content as requirement context.

**Linked issue = requirement — huge enrichment value**
- STWA-10 (Epic, "Blocks" STWA-9) contains the functional requirement:
  *"uprawniony użytkownik ma mieć możliwość utworzenia, zapisania i zmiany statusów Leada"*
- Enricher fetches linked issues and passes requirement text to AI prompt → much richer context.

---

### 💬 Selector in comment — gold for Playwright Writer

**Tester left CSS selector in a comment**
- STWA-9, comment: `#\31 2497\:0 > div > div.slds-grid.slds-path__action... > button > span`
- This is a Salesforce LWC dynamically-generated selector — would be nearly impossible to derive from screenshot alone.
- Comments included in AI prompt → selectors mentioned in comments → `ui_elements` in enriched output → Playwright `locator()` calls.

---

### 🔢 Completeness score parser bug

**Score `10/100` parsed as `101/100`**
- AI responded with `KOMPLETNOŚĆ: 10 / 100 (...)` — parser extracted `101` instead of `10`.
- Fix: explicit regex `(\d{1,3})\s*/\s*100`, clamp `0–100`, heuristic fallback when AI returns `< 30`.

---

### 🔒 SSL / certifi — Windows Microsoft Store Python

**Python from Microsoft Store doesn't inherit Windows certificate trust chain**
- `curl` (PowerShell) connected fine — Windows trusted the Atlassian cert.
- Python `requests` failed with `CERTIFICATE_VERIFY_FAILED` — MS Store Python uses isolated certstore.
- Fix: `pip install pip-system-certs` — bridges Windows CertStore into Python's SSL context, zero code changes.
- **Lesson:** If it worked before and broke now → suspect certifi bundle rotation or Windows Update touching cert chain.

---

### 📋 Completeness checklist — proposed standard (Sprint 3 input)

Based on field testing with STWA-9, a defect report is "complete" when it contains:

| Field | Source | Status in STWA-9 |
|-------|--------|-----------------|
| Steps to reproduce | description / AI | ✅ extracted by AI |
| Expected result | description / AI | ✅ extracted |
| Actual result | description / AI | ✅ extracted |
| URL / navigation path | description `<a href>` / ADF inlineCard | ✅ fixed |
| Error message | description / screenshot | ✅ AI correctly said "not visible" |
| Screenshot | attachment | ✅ present |
| Requirement reference | title / linked issue | ✅ STWA-10 fetched |
| CSS/UI selector | comment | ✅ passed to AI prompt |
| Environment (browser, OS, role) | environment field / description | ⚠️ defaults assumed |
| Assignee / reporter | Jira fields | ✅ |

---

## Sprint 2 — field testing observations (June 2026)

### 🤖 llava limitations — documented from real testing

**Tested on:** STWA-9 (Lead status bug), STWA-12 (UX/frontend bug), STWA-13 (Opportunity save error)

**llava hallucinations — the most dangerous failure mode:**
- **Fabricates URLs** when none are present — returned `https://example-frontend.com` for STWA-12 which had no URL. A hallucinated URL in a retest script = script navigates to wrong place.
- **Invents element names** — `OpportunityId`, `SaveButton` — plausible-sounding but not verified against actual DOM.
- **Copies CSS selector into wrong sections** — when uncertain about requirement refs or error messages, pastes the CSS selector there instead.
- **Mitigation:** Generated scripts mark AI-inferred selectors as `# TODO: verify selector`.

**llava inconsistency — scoring and formatting:**
- Completeness score varies wildly (0, 10, 50, 100) across runs on similar-quality reports.
- Mutates Polish section headers with random diacritics: `BRAKUJĄCe`, `BRAKUJĄCią`, `KOMPLETNÓŚĆ` — parser misses these sections silently.
- Sometimes outputs `**HEADER:**` (bold + colon) — gap in `_is_section_header()`.

**llava strengths:**
- Picks up URL from comments when missing from description ✅
- Reads screenshot and identifies visible UI state ✅
- Extracts error message from title when description is empty ✅
- Correctly scores incomplete reports lower than complete ones (relative) ✅

---

### 🛡️ Issue type guard — implemented in Sprint 3

- Nothing stops a tester from running defect-pilot on an Epic, Story, or Task.
- Guard added in `run_retest.py` — checks `issue_type` against configurable list.
- Configurable via `.env`: `SUPPORTED_ISSUE_TYPES=bug,błąd,defect,error,problem`
- Never hardcoded — locale variance ("Błąd" = "Bug" = "Defect" on different projects).

---

### 🎬 Video attachments — parked for later

- Manual testers sometimes record screen walkthroughs (`.mp4`, `.mov`) instead of writing steps.
- Current: `_is_image()` filters by MIME type — videos silently skipped.
- Planned: explicit warning when video detected.
- Future (Sprint 5+): extract keyframes via `ffmpeg`, send as images to vision model.

---

### 🔗 URL in comments — works via AI, gap in parser

- STWA-13: tester put Opportunity URL in a comment — llava picked it up correctly.
- Gap: `jira_reader.py` only extracts URLs from description ADF, not comment bodies.
- Future: apply same URL extraction to comment ADF.

---

## Sprint 3 — Playwright Writer (June 2026)

### 🎭 Option C — deterministic template (chosen for v1)

**Three options evaluated:**

| Option | Approach | Privacy | Quality | Chosen? |
|--------|----------|---------|---------|---------|
| A | Ollama generates Playwright code | ✅ Local | ⚠️ Poor — llava bad at code | No |
| B | Claude/Anthropic generates code | ❌ Data leaves machine | ✅ Excellent | Future |
| C | Deterministic template + EnrichedDefect data | ✅ Local | ✅ Predictable | **v1** |

**Why Option C:**
- No AI in script generation = no hallucinated Playwright calls
- Every gap marked with `# TODO` — honest, auditable
- Output quality bounded by enrichment quality — makes enrichment gaps visible
- `# TODO: verify selector` in every AI-inferred selector — tester knows what to check

**Option B planned for v2** — when we add explicit data-out consent flag to config.

---

### 🏗️ Architecture additions — Sprint 3

**`retest/shared/sf_login.py`** — Salesforce Lightning login helper:
- Reads `SF_BASE_URL`, `SF_USERNAME`, `SF_PASSWORD` from `.env`
- Handles login form, waits for Lightning Experience to load
- Raises `EnvironmentError` if credentials missing — fails fast, clear message
- Imported by every generated retest script: `from retest.shared.sf_login import login`

**`retest/playwright_writer.py`** — deterministic script generator:
- `generate(enriched)` → Python script string
- `save(enriched)` → writes to `retest/scripts/retest_{ISSUE_KEY}.py`
- Heuristic step mapping: "navigate/go to/open" → skip (handled in Navigate section), "click" → `get_by_role()`, "fill" → `page.fill()` TODO
- Shadow DOM detection: Aura IDs (`#\31...`) and SLDS classes → `pierce/` prefix
- `_needs_fresh_data()` heuristic: CRUD keywords in steps/summary → COMPLEX warning
- `_clean_url()` — strips llava markdown angle brackets `<https://...>` → `https://...`

**`scripts/run_retest.py`** — CLI entry point:
- `--issue` required, `--url` override, `--debug`, `--dry-run`
- Full pipeline: Jira fetch → issue type guard → enrichment → script generation
- `--dry-run` prints to stdout without saving — safe for testing

---

### 🧪 Test Data Problem — core challenge for retest scripts

**Problem:** Retest script with hardcoded Salesforce record URL (`/r/Lead/00Qd200000XByc9EAD/view`) fails if:
- Record was closed, converted, or deleted since bug was filed
- Environment was refreshed with new data

**v1 solution:** `RECORD_URL` with `os.getenv("RETEST_URL", "<url_from_bug>")` — tester can override at runtime.

**Two retest modes (Sprint 4 design):**

| Mode | When | Action |
|------|------|--------|
| **Simple** | Navigation + click + check, no CRUD, existing data OK | Auto-retest via Playwright + screenshots + result in Jira |
| **Complex** | CRUD involved, fresh data needed, multi-step setup | Comment to tester: "Prepare test data, provide URL" → retest on prepared data |

**Heuristic for simple vs complex:** `_needs_fresh_data()` — CRUD keywords in steps/summary. To be refined in Sprint 4.

---

### ⚠️ Salesforce + Playwright — IP whitelist required

- SF Developer Edition blocks logins from unrecognized IPs — sends email verification code.
- Playwright cannot handle email verification flow.
- Fix: `Setup → Network Access → New` — add dev machine IP.
- Dynamic IP problem: home ISP changes IP periodically → re-add to whitelist or disable IP restriction for dev profile.
- `Setup → Session Settings` → uncheck "Lock sessions to the IP address from which they originated" — prevents session reset on IP change.

---

## 🔄 Vision pivot — defect-pilot as QA gatekeeper (June 2026)

### The original vision vs the evolved vision

**Original:** "Lazy tester helper" — enriches incomplete bug reports so devs don't have to play detective.

**Evolved:** defect-pilot as a **QA process gatekeeper** — an automated layer between tester and developer that enforces quality standards and closes the retest loop.

### New end-to-end flow

```
Tester zgłasza buga w Jira
        ↓
Alokuje na "AI_agent" (dedykowany service account)
        ↓
⏰ Scheduler — poll co 5 min
   JQL: assignee = AI_agent AND status = "Do zrobienia" AND updated >= -10m
        ↓
📥 JiraReader — parsuje zgłoszenie
        ↓
🤖 DefectEnricher — sprawdza kompletność vs checklist
        ↓
    ┌─────────────────────────────────────────┐
    │ Krytyczne braki?                        │
    │ (przez które ollama bredzi)             │
    │ - brak URL                              │
    │ - brak opisu co się dzieje              │
    │ - brak screenshota (UI bug)             │
    └─────────────────────────────────────────┘
         ↓ TAK                    ↓ NIE
  📤 Komentarz z listą       📤 Enriched comment
  braków do testera          realokacja do deva
  realokacja do zgłaszającego
        ↓
  Tester uzupełnia i alokuje znowu na AI_agent
        ↓
⏰ Scheduler — po okienku wdrożeniowym
   Defekt zmienił właściciela z opisem "fixed"?
        ↓
    ┌─────────────────────────────┐
    │ Prosty case?                │
    │ - nawigacja + klik + check  │
    │ - brak CRUD                 │
    │ - dane z bug reportu OK     │
    └─────────────────────────────┘
         ↓ TAK                    ↓ NIE (złożony)
  🎭 Auto-retest             💬 Komentarz do testera:
  Playwright + screenshoty   "Przygotuj dane do retestu
  wynik w Jira               i podaj URL w komentarzu"
                                    ↓
                             Tester przygotowuje dane
                                    ↓
                             🎭 Playwright na gotowcu
                             + screenshoty + wynik w Jira
```

### Why this matters

- **Tester** — dostaje konkretną listę braków zamiast odrzuconego ticketa bez wyjaśnienia
- **Dev** — dostaje tylko kompletne zgłoszenia, zero "co to znaczy?"
- **QA Lead** — widzi metryki: % zwróconych zgłoszeń, średni czas enrichmentu, % auto-retestów
- **Projekt** — krótszy cykl bug → fix → retest → zamknięty

### AI_agent in Jira

- Dedykowany service account w Jira — tester alokuje buga zamiast na deva
- Scheduler odpytuje JQL: `assignee = AI_agent AND status = "Do zrobienia" AND updated >= -10m`
- Poll co 5 min — wystarczający dla procesu QA, nie przeciąża Jira API
- `APScheduler` lub prosty `schedule` library

### Krytyczne braki vs ostrzeżenia

| Krytyczne — zwrot do testera | Ostrzeżenie — enrichujemy mimo to |
|------------------------------|----------------------------------|
| Brak URL / środowiska | Brak wymagania |
| Brak opisu co się dzieje | Brak selektora |
| Brak screenshota (UI bug) | Niejasne kroki |
| Opis = sam tytuł przepisany | Brak expected result |

**Definicja robocza krytycznych braków:** "braki przez które ollama bredzi" — zweryfikowane na STWA-12 (halucynowany URL) i STWA-13 (actual result = tytuł).

---

_Next update: after Sprint 4 — Jira Updater + Scheduler + Gatekeeper logic_

---

### 📋 Option C — honest assessment after first real script

**What we got:** `retest_STWA_9.py` — login + navigation + one `get_by_role().click()` + `pass`.

**What we didn't get:** assertions, wait strategies, error handling, anything that makes it a real retest.

**Root cause:** Option C (deterministic template) can map steps to Playwright calls heuristically, but cannot generate meaningful assertions without knowing *what to check after the action* — and that requires understanding the expected UI state in a way that needs structured `assertion_target` data, not free-text `expected_result`.

**Practical consequence:** A tester would need to manually add assertions, selectors, and wait conditions before the script is runnable. For a simple 3-step retest, this manual work could easily take longer than just clicking through the app manually. **Option C produces a documentation artifact, not a working automat.**

**Decision: move to Option B (Claude generates full script)**
- Option C → parked as fallback for air-gapped / strict NDA environments
- Option B → default when `SCRIPT_GENERATION=cloud` in `.env`
- Explicit consent required — CLI warning before sending data to Anthropic API
- Config: `SCRIPT_GENERATION=local|cloud` — tester/admin chooses consciously

**What Option B will give us that Option C cannot:**
- Meaningful assertions based on expected result context
- Proper `expect()` calls with correct locators
- `wait_for_selector` / `wait_for_load_state` in right places
- Overall: a script that actually retests the bug, not just clicks in its direction

---

_Next update: after Sprint 4 — Option B script generation + Jira Updater + Scheduler_

---

### ⚠️ Gemini free tier — blocked despite correct setup (June 2026)

**Problem:** `GeminiProvider` integration was technically correct — connection succeeded, model initialized, request sent — but every call returned `429 RESOURCE_EXHAUSTED` with `limit: 0` for all quota metrics (requests/day, requests/minute, input tokens/minute), across multiple models (`gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-flash`).

**Troubleshooting steps taken (all failed to resolve):**
1. Tried multiple Gemini models — same `limit: 0` on all
2. Enabled Generative Language API explicitly in Google Cloud Console
3. Created a brand new Google Cloud project with a fresh API key — same result
4. Verified Poland is on the [supported regions list](https://ai.google.dev/gemini-api/docs/available-regions) — confirmed
5. Attached a billing account (credit card) to the project — still `limit: 0`

**Conclusion:** This appears to be an account-level restriction on Google's side, not a configuration issue on ours. Possibly: new-account cooldown period, undisclosed regional throttling, or a flag specific to this Google account that isn't documented. The `google-genai` SDK and our `GeminiProvider` implementation work correctly — verified by clean request/response cycle, just blocked by quota enforcement before any content is returned.

**Decision: pivot Option B to OpenAI (`gpt-4o-mini`)**
- Stable, well-documented quota system
- Very low cost (~$0.15/1M input tokens) — a few cents covers hundreds of script generations
- No free-tier ambiguity — pay-as-you-go from a small prepaid credit

**Lesson for future provider integration:** Don't assume "free tier" literally means zero friction. Budget troubleshooting time for account-level quirks that have nothing to do with code correctness. If 3+ independent fixes (new project, new key, billing) don't resolve a `limit: 0`, stop debugging and switch providers — the issue is likely outside your control.