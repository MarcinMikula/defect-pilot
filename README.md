# 🛩️ defect-pilot

> AI-powered QA gatekeeper — enriches bug reports, enforces quality standards,
> generates Playwright retest scripts, and closes the bug lifecycle loop automatically.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![Playwright](https://img.shields.io/badge/Playwright-latest-green)
![Jira](https://img.shields.io/badge/Jira-Cloud-blue)
![AI](https://img.shields.io/badge/AI-Ollama%20%7C%20Anthropic-purple)
![CI](https://img.shields.io/badge/CI-GitHub%20Actions-black)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🧠 The problem

A Jira defect from a manual tester can look like this:

> **Title:** "OPL-SF-008 — Cannot save individual customer account,
> clicking Save results in an error"
>
> **Description:** "I was testing individual customer account creation.
> After filling in the form and entering the PESEL number I clicked Save
> and got a validation error. Same issue when entering postal code.
> See screenshot."
>
> **Attachment:** screenshot.png *(problematic element circled in Paint)*  
> **Steps to reproduce:** *(empty)*  
> **Selectors / element IDs:** *(never)*  
> **URL:** *(forgotten)*

The tester knows what they did. The screenshot shows the outcome.
But without reproduction steps, URL, and element selectors:
- The dev still plays detective
- The tester doing retest still clicks through the whole flow manually
- The QA lead has no visibility into report quality

**defect-pilot fills that gap** — automatically.

---

## ✅ How it works

defect-pilot acts as a **gatekeeper** between tester and developer:

```
Tester files bug → assigns to AI_agent in Jira
        ↓
⏰  Scheduler polls Jira every 5 min (JQL: assignee = AI_agent)
        ↓
📥  JiraReader — fetches issue, parses ADF, extracts URLs,
                 downloads screenshots, fetches linked requirements
        ↓
🤖  DefectEnricher — AI analyzes text + images, checks completeness checklist
        ↓
        ├── Critical gaps? (missing URL, no description, no screenshot)
        │       ↓ YES
        │   📤 Comment with gap list → reassign back to tester
        │       ↓ (tester fills gaps, reassigns to AI_agent)
        │
        └── Complete? ↓ YES
            📤 Enriched comment → reassign to developer
                ↓
⏰  Scheduler — after deployment window closes
    Bug reassigned with "fixed" note?
        ↓
        ├── Simple retest? (navigation + click, no CRUD, existing data OK)
        │       ↓ YES
        │   🎭 Playwright auto-retest + screenshots → result in Jira
        │
        └── Complex retest? (CRUD, fresh data needed)
                ↓ YES
            📤 Comment to tester: "Prepare test data, provide URL"
                ↓ (tester prepares data)
            🎭 Playwright retest on prepared data + screenshots → result in Jira
```

### What AI extracts from a minimal defect report:

| Field | Source |
|-------|--------|
| Structured reproduction steps | Description text + screenshot |
| Expected vs actual result | Inferred from context |
| URL where bug occurred | ADF inlineCard, link marks, or comment |
| UI elements & selectors | Screenshot analysis + tester comments |
| Error message | Screenshot (vision) or description |
| Requirement text | Linked issues (Epics, Stories) fetched automatically |
| Completeness score (0-100) | How reproducible is this ticket? |
| Missing information | What the tester forgot to write |
| Simple vs complex retest | CRUD keyword heuristic |

---

## 🔒 Privacy-first AI design

Many QA teams work under NDAs or data residency requirements.
**Jira tickets are documentation — they can't leave the machine without explicit consent.**

defect-pilot solves this with a **pluggable AI provider** and a **two-stage data policy**:

| Stage | Provider | Data leaves machine? |
|-------|----------|---------------------|
| Enrichment (analysis) | `ollama` (local) | ❌ Never |
| Script generation | `gemini` (cloud) | ✅ Yes — explicit consent required |

**Enrichment is always local.** Script generation via Gemini is opt-in:

```env
SCRIPT_GENERATION=local   # Option C — deterministic template, no AI, fully private
SCRIPT_GENERATION=cloud   # Option B — Gemini generates full working script
```

When `cloud` is set, CLI shows an explicit warning and requires confirmation before sending data.

| Provider | Role | Data leaves machine? |
|----------|------|---------------------|
| `ollama` | Enrichment — always local | ❌ Never |
| `gemini` | Script generation (Option B) | ✅ Yes — opt-in |
| `anthropic` | Alternative enrichment provider | ✅ Yes |
| `openai` | _(planned)_ | ✅ Yes |

---

## 🏗️ Architecture

```
defect-pilot/
├── agent/
│   ├── jira_reader.py        # Fetches & parses Jira (ADF, URLs, attachments, linked issues)
│   ├── defect_enricher.py    # AI enrichment — text + vision, completeness scoring
│   └── jira_updater.py       # Writes enriched data + results back to Jira (Sprint 4)
├── ai/
│   ├── base_provider.py      # Abstract base — add new providers in one file
│   ├── anthropic_provider.py # Claude (vision supported)
│   ├── ollama_provider.py    # Local LLM (vision: model-dependent)
│   ├── gemini_provider.py    # Gemini — script generation (Sprint 5)
│   └── provider_factory.py   # Instantiates provider from config
├── retest/
│   ├── playwright_writer.py  # Script generator — Option C (local) or Option B (Gemini)
│   ├── shared/
│   │   └── sf_login.py       # Salesforce Lightning login helper
│   └── scripts/              # Generated retest scripts (per issue)
│       └── retest_STWA_9.py  # Example generated script
├── db/
│   └── defect_store.py       # SQLite — local defect lifecycle tracking
├── config/
│   └── settings.py           # .env loader and validation
├── scripts/
│   ├── run_enrichment.py     # CLI — enrich a single issue
│   └── run_retest.py         # CLI — generate retest script for an issue
└── tests/
    ├── unit/                 # Unit tests, all mocked
    └── integration/          # Integration tests (live credentials required)
```

---

## 🚀 Quickstart

```bash
# 1. Clone
git clone https://github.com/MarcinMikula/defect-pilot.git
cd defect-pilot

# 2. Install
pip install -r requirements.txt
playwright install chromium

# 3. Configure
cp .env.example .env
# Edit .env — Jira credentials, AI provider, Salesforce credentials

# 4. Enrich a bug report
python scripts/run_enrichment.py --issue PROJ-123
python scripts/run_enrichment.py --issue PROJ-123 --debug

# 5. Generate retest script
python scripts/run_retest.py --issue PROJ-123
python scripts/run_retest.py --issue PROJ-123 --dry-run --debug

# 6. Run generated retest
pytest retest/scripts/retest_PROJ_123.py -v
```

---

## ⚙️ Configuration

`.env` file:

```env
# AI Provider for enrichment: "anthropic" or "ollama"
AI_PROVIDER=ollama

# Anthropic (if AI_PROVIDER=anthropic)
ANTHROPIC_API_KEY=sk-ant-...

# Ollama (if AI_PROVIDER=ollama)
# Prerequisites: install https://ollama.com, then:
#   ollama serve
#   ollama pull llava        # vision support (recommended)
#   ollama pull llama3.2     # text-only fallback
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llava

# Gemini (for script generation — Option B)
# Free tier: https://aistudio.google.com/apikey
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash

# Jira
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=your-token-here
JIRA_PROJECT_KEY=PROJ

# Salesforce (for retest scripts)
SF_BASE_URL=https://your-instance.trailblaze.lightning.force.com
SF_USERNAME=user@instance.com
SF_PASSWORD=your-sf-password

# Retest configuration
SCRIPT_GENERATION=cloud      # "local" = Option C (private), "cloud" = Option B (Gemini)
RETEST_URL=                  # override stale record URL from bug report
SUPPORTED_ISSUE_TYPES=bug,błąd,defect,error,problem
```

> ⚠️ **Jira configuration variance:** Every Jira instance is configured differently.
> Issue type names, link types, and custom fields vary per project and locale (PL/EN).
> defect-pilot stores all values as raw strings — never hardcoded.
> See [LEARNINGS.md](LEARNINGS.md) for the full variance table.

---

## 🤖 AI provider notes

**Ollama (local, privacy-first) — used for enrichment:**
- Vision requires a vision-capable model — `llava` recommended, `llama3.2` is text-only
- `WinError 10061` = Ollama process not running — run `ollama serve` first
- Known limitation: llava occasionally hallucinates URLs or element names when data is missing
- Generated scripts mark all AI-inferred selectors with `# TODO: verify` — always check before running

**Gemini (cloud) — used for script generation:**
- Free tier available at https://aistudio.google.com/apikey — no credit card required
- Generates complete, working Playwright scripts with meaningful assertions
- Data sent: enriched defect data (steps, URL, expected/actual, UI elements) — not raw Jira ticket
- Requires explicit confirmation in CLI before sending

**Script generation modes:**
- `SCRIPT_GENERATION=local` — Option C: deterministic template, no AI, fully private. Produces a skeleton that requires manual assertion writing. Good for air-gapped environments.
- `SCRIPT_GENERATION=cloud` — Option B: Gemini generates complete script with assertions. Recommended for quality.

---

## 🗺️ Roadmap

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 0 | Repo scaffold, config, AI provider stubs | ✅ Done |
| Sprint 1 | Jira Reader — ADF parsing, attachments, comments, issue links | ✅ Done |
| Sprint 2 | AI Enricher — multimodal (text + vision), bilingual, linked requirements | ✅ Done |
| Sprint 3 | Playwright Writer — Option C (deterministic template, SF login) | ✅ Done |
| Sprint 3a | Script generation evaluation — Option C vs B, decision: Gemini for Option B | ✅ Done |
| Sprint 4 | Jira Updater + Gatekeeper + Scheduler (AI_agent flow) | 🔄 Next |
| Sprint 5 | Option B (Gemini script generation) + Allure + CLI polish + demo GIF | ⏳ Planned |

---

## 🧪 Test environment

UAT runs against:
- **Jira Cloud** — real instance (`STWA` project), synthetic defects reflecting real-world patterns
- **Salesforce Developer Edition** — free instance, Lightning Experience, Shadow DOM via LWC

---

## 📓 Project diary

See [LEARNINGS.md](LEARNINGS.md) for architectural decisions, lessons learned, the vision pivot from "lazy tester helper" to "QA gatekeeper", and honest notes from every sprint.

---

## 🤝 Contributing

PRs welcome. Open an issue first for major changes.

---

## 📄 License

MIT