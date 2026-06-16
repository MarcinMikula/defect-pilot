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

**Proposed feature (Sprint 4):**
- Configurable scheduler: set time + days in `.env` or `config.yml`
- Agent polls Jira after deployment window: finds issues with status "Ready for retest" / "Do retestu" (configurable — locale variance again!)
- Triggers retest script generation automatically
- Notifies tester (log, file, optional Slack/email)

**Config sketch:**
```yaml
retest_scheduler:
  enabled: true
  check_after: "14:00"
  days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
  retest_status: "Ready for retest"
  timezone: "Europe/Warsaw"
```

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
| `gemini` | Free tier, good code generation, 1M context window |
| `openai` | GPT-4o vision, widely adopted in enterprise |

Both = single new file + one line in `provider_factory.py`. Architecture already supports it.

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
3. Generates a Playwright retest script (done ✅)
4. Updates Jira with enriched data + acts as gatekeeper (Sprint 4)

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
- Example: `<span data-aura-rendered-by="12539:0" class="uiOutputText">Mark Status as Complete</span>`
- Fix: `strip_html()` in `jira_reader.py` — strips tags, keeps inner text.
- Commit: `fix: strip HTML tags from Jira fields (Salesforce ADF span injection)`

**⚠️ HTML strip also strips URLs — data loss**
- `<a href="https://...">` links stripped along with `<span>` tags.
- Fix: extract `href` before stripping. ADF inlineCard nodes also carry URLs.
- `_adf_to_text()` extended with `_urls` collector — handles both link marks and `inlineCard` nodes.

**RSS export ≠ REST API v3 — again**
- RSS shows HTML with `<a href>` visible. REST API v3 returns ADF JSON.
- Always test against REST API, not RSS export.

---

### 🔗 Issue links — fetch linked requirements

- STWA-9 linked to STWA-10 (Epic with functional requirement).
- `get_linked_issues()` added to `JiraReader` — fetches full content of linked issues.
- Requirement text passed to AI prompt as `requirement_context` → richer enrichment.

---

### 💬 Selector in comment — gold for Playwright Writer

- STWA-9 comment contained Salesforce LWC CSS selector — impossible to derive from screenshot alone.
- Comments included in AI prompt → selectors flow through to `ui_elements` → Playwright `locator()`.

---

### 🔢 Completeness score — parser bug + heuristic fallback

- Parser bug: `10/100` parsed as `101/100` — fixed with `re.search(r'\d{1,3}', score_raw)` + clamp `0–100`.
- llava inconsistency: scores 0/10/50/100 on similar reports — heuristic fallback when AI returns `< 30`.
- Heuristic weights: steps(25) + url(20) + expected(15) + actual(15) + screenshot(10) + ui_elements(10) + refs(5).

---

### 🔒 SSL / certifi — Windows Microsoft Store Python

- MS Store Python doesn't inherit Windows certificate trust chain.
- Fix: `pip install pip-system-certs` — zero code changes.
- Lesson: if it worked before and broke now → suspect certifi bundle rotation or Windows Update.

---

### 📋 Completeness checklist

| Field | Status after Sprint 2 fixes |
|-------|----------------------------|
| Steps to reproduce | ✅ AI extracts |
| Expected / actual result | ✅ AI extracts |
| URL / navigation path | ✅ ADF inlineCard + link marks |
| Error message | ✅ AI from screenshot/description |
| Screenshot | ✅ downloaded + sent to vision model |
| Requirement reference | ✅ linked issue fetched |
| CSS/UI selector | ✅ from comments via AI prompt |
| Environment | ⚠️ defaults assumed (Chrome/Windows) |

---

## Sprint 2 — field testing observations (June 2026)

### 🤖 llava limitations — documented from real testing

**Tested on:** STWA-9, STWA-12, STWA-13

**Hallucinations — most dangerous failure mode:**
- Fabricates URLs: returned `https://example-frontend.com` for STWA-12 (no URL in report)
- Invents element names: `OpportunityId`, `SaveButton` — plausible but unverified
- Copies CSS selector into wrong sections (requirement refs, error message)
- Mitigation: generated scripts mark AI-inferred selectors with `# TODO: verify`

**Inconsistency:**
- Completeness score: 0, 10, 50, 100 across runs on similar reports
- Mutates Polish headers: `BRAKUJĄCe`, `BRAKUJĄCią`, `KOMPLETNÓŚĆ` — parser misses them
- Sometimes outputs `**HEADER:**` (bold + colon) — gap in `_is_section_header()`

**Strengths:**
- Picks up URL from comments when missing from description ✅
- Reads screenshot, identifies UI state ✅
- Extracts error message from title when description is empty ✅

---

### 🛡️ Issue type guard

- Configurable via `.env`: `SUPPORTED_ISSUE_TYPES=bug,błąd,defect,error,problem`
- Implemented in `run_retest.py` — fails fast with clear message if wrong type
- Never hardcoded — "Błąd" = "Bug" = "Defect" on different projects

---

### 🎬 Video attachments — parked

- Testers sometimes record `.mp4`/`.mov` walkthroughs instead of writing steps
- Current: silently skipped by `_is_image()`
- Planned: explicit warning; future Sprint 5+: ffmpeg keyframe extraction

---

### 🔗 URL in comments — works via AI, gap in parser

- STWA-13: URL in comment → llava picked it up correctly
- Gap: `jira_reader.py` doesn't extract URLs from comment ADF — future improvement

---

## Sprint 3 — Playwright Writer Option C (June 2026)

### 🏗️ Architecture additions

**`retest/shared/sf_login.py`** — Salesforce Lightning login:
- Reads `SF_BASE_URL`, `SF_USERNAME`, `SF_PASSWORD` from `.env`
- Handles login form + waits for Lightning to load
- Raises `EnvironmentError` if credentials missing — fails fast

**`retest/playwright_writer.py`** — deterministic generator:
- `generate(enriched)` → Python script string
- `save(enriched)` → writes to `retest/scripts/retest_{ISSUE_KEY}.py`
- Heuristics: "navigate/go to" → skip (already in Navigate section), "click" → `get_by_role()`, "fill" → TODO
- Shadow DOM detection: Aura IDs + SLDS classes → `pierce/` prefix
- `_needs_fresh_data()`: CRUD keywords → COMPLEX warning in script
- `_clean_url()`: strips llava markdown angle brackets `<https://...>` → `https://...`

**`scripts/run_retest.py`** — CLI entry point:
- `--issue`, `--url` override, `--debug`, `--dry-run`
- Full pipeline: Jira fetch → issue type guard → enrichment → script generation

### ⚠️ Salesforce + Playwright — IP whitelist

- SF blocks logins from unrecognized IPs — sends email verification
- Fix: `Setup → Network Access` → add dev machine IP
- Dynamic IP problem: `Setup → Session Settings` → uncheck "Lock sessions to IP"

---

## Sprint 3a — Script generation evaluation (June 2026)

### 📋 Option C vs Option B — honest comparison

**What Option C (deterministic template) produced for STWA-9:**

```python
def test_retest_stwa_9(page: Page) -> None:
    login(page)
    page.goto(RECORD_URL)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Mark Status as Complete").click()  # TODO: verify
    pass  # no assertion
```

**Assessment:** Not a working retest. It clicks the button and declares success regardless of what happens. A tester would need to manually add assertions, selectors, and wait conditions — work that could easily take longer than clicking through the app manually.

**Option C is a documentation artifact, not an automat.**

---

### 🔄 Decision: Option B with Gemini

**Three options evaluated:**

| Option | Approach | Privacy | Quality | Decision |
|--------|----------|---------|---------|----------|
| A | Ollama generates Playwright code | ✅ Local | ❌ Poor — llava bad at code generation | Rejected |
| C | Deterministic template | ✅ Local | ⚠️ Skeleton only — requires manual assertions | Fallback for air-gapped |
| B | External LLM generates full script | ⚠️ Cloud | ✅ Complete working script with assertions | **Chosen** |

**Why Gemini for Option B:**
- Free tier — no credit card, no cost for portfolio/demo use
- Good code generation quality, especially Python
- Separate from enrichment provider — data sent only once for script generation, not on every enrichment run
- `gemini-2.0-flash` — fast, free, sufficient quality

**Two-stage data policy:**
- Enrichment (ollama) → always local, data never leaves machine
- Script generation (Gemini) → opt-in via `SCRIPT_GENERATION=cloud`, explicit CLI warning + confirmation

**What Option B will produce:**
```python
def test_retest_stwa_9(page: Page) -> None:
    login(page)
    page.goto(RECORD_URL)
    page.wait_for_load_state("networkidle")

    button = page.get_by_role("button", name="Mark Status as Complete")
    button.wait_for(state="visible", timeout=10_000)

    # Bug: button should be enabled — assert FAILS when bug is present
    expect(button).to_be_enabled()
```

**Option C kept as `SCRIPT_GENERATION=local`** — valid choice for NDA/air-gapped environments where even script generation data cannot leave the machine. Documented limitation: requires manual assertion writing.

---

## 🔄 Vision pivot — defect-pilot as QA gatekeeper (June 2026)

### Original vision vs evolved vision

**Original:** "Lazy tester helper" — enriches incomplete bug reports so devs don't have to play detective.

**Evolved:** defect-pilot as a **QA process gatekeeper** — an automated layer between tester and developer that enforces quality standards and closes the retest loop.

### New end-to-end flow

```
Tester zgłasza buga → alokuje na AI_agent w Jira
        ↓
⏰ Scheduler — poll co 5 min
   JQL: assignee = AI_agent AND status = "Do zrobienia" AND updated >= -10m
        ↓
📥 JiraReader + 🤖 DefectEnricher
        ↓
    Krytyczne braki?
    (przez które ollama bredzi)
         ↓ TAK                      ↓ NIE
  📤 Komentarz z listą braków   📤 Enriched comment
  realokacja do testera          realokacja do deva
        ↓
  Tester uzupełnia, alokuje znowu
        ↓
⏰ Scheduler — po okienku wdrożeniowym
   Bug zmienił właściciela z opisem "fixed"?
        ↓
    Prosty case?
    (nawigacja + klik, brak CRUD, dane OK)
         ↓ TAK                      ↓ NIE (złożony)
  🎭 Auto-retest               💬 "Przygotuj dane
  + screenshoty                do retestu, podaj URL"
  + wynik w Jira                      ↓
                               Tester przygotowuje
                                      ↓
                               🎭 Playwright na gotowcu
                               + screenshoty + wynik
```

### Why this matters

- **Tester** — dostaje konkretną listę braków zamiast odrzuconego ticketa
- **Dev** — dostaje tylko kompletne zgłoszenia
- **QA Lead** — widzi metryki: % zwróconych zgłoszeń, % auto-retestów
- **Projekt** — krótszy cykl bug → fix → retest → zamknięty

### AI_agent in Jira

- Dedykowany service account — tester alokuje buga zamiast na deva
- Scheduler: JQL `assignee = AI_agent AND status = "Do zrobienia" AND updated >= -10m`
- Poll co 5 min — wystarczający dla procesu QA, nie przeciąża Jira API
- `APScheduler` lub prosty `schedule` library

### Krytyczne braki vs ostrzeżenia

| Krytyczne — zwrot do testera | Ostrzeżenie — enrichujemy mimo to |
|------------------------------|----------------------------------|
| Brak URL | Brak wymagania |
| Brak opisu co się dzieje | Brak selektora |
| Brak screenshota (UI bug) | Niejasne kroki |
| Opis = sam tytuł przepisany | Brak expected result |

**Definicja robocza:** "braki przez które ollama bredzi" — zweryfikowane na STWA-12 (halucynowany URL) i STWA-13 (actual = tytuł).

### Test Data Problem — simple vs complex retest

**Simple retest** (auto):
- Nawigacja + klik + check
- Brak operacji CRUD
- Dane z bug reportu nadal aktualne

**Complex retest** (semi-auto):
- Wymaga świeżych danych (Lead, Opportunity, Account)
- Rekord z bug reportu może być zamknięty/usunięty
- Tester przygotowuje dane → podaje URL → Playwright wykonuje retest

Heurystyka w `_needs_fresh_data()`: CRUD keywords (create, save, add, delete, convert, lead, opportunity...) w steps/summary → COMPLEX.

---

_Next update: after Sprint 4 — Jira Updater + Gatekeeper + Scheduler_