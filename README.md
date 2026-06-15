# 🛩️ defect-pilot

> AI-powered bug reproduction & retest agent for QA engineers.  
> Reads Jira defects, enriches them with technical context, generates Playwright retest scripts — locally or via API.

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
> **Steps to reproduce:** *(empty or vague)*  
> **Selectors / element IDs:** *(never)*

The tester knows what they did and what they expected. The screenshot
shows the outcome — the body at the crime scene. But without reproduction
steps and element selectors, the dev still plays detective, and the tester
doing retest still clicks through the whole flow manually.

**defect-pilot fills that gap** — it reconstructs the steps from context,
infers likely UI elements and interaction targets from defect context
(description, title, screenshots, comments, and linked requirements).
Root cause analysis stays with the dev. Everything else gets automated.

---

## ✅ The solution

```
Jira defect (minimal)
    ↓
📥  JiraReader      — fetches issue, parses ADF, extracts URLs, downloads screenshots,
                      fetches linked issues (requirements, epics)
    ↓
🤖  DefectEnricher  — AI analyzes text + images, extracts structured context,
                      scores completeness (0-100), identifies missing information
    ↓
🎭  PlaywrightWriter — generates flat retest script (Sprint 3)
    ↓
📤  JiraUpdater     — enriched data + script written back to Jira as comment (Sprint 4)
    ↓
💾  DefectStore     — local SQLite tracks defect lifecycle (Sprint 4)
```

### What AI extracts from a minimal defect report:

| Field | Source |
|-------|--------|
| Structured reproduction steps | Description text + screenshot |
| Expected vs actual result | Inferred from context |
| URL where bug occurred | ADF inlineCard, link marks, or comment |
| UI elements & selectors | Screenshot analysis + comments |
| Error message | Screenshot (vision) or description |
| Requirement references | Linked issues (Epics, Stories) fetched automatically |
| Completeness score (0-100) | How reproducible is this ticket? |
| Missing information | What the tester forgot to write |

---

## 🔒 Privacy-first AI design

Many QA teams work under NDAs or data residency requirements.  
**Jira tickets are documentation — they can't be sent to external APIs without consent.**

defect-pilot solves this with a **pluggable AI provider**:

| Provider | When to use | Data leaves machine? |
|----------|-------------|---------------------|
| `ollama` | NDA / air-gapped / local | ❌ Never |
| `anthropic` | Cloud projects, best quality | ✅ Yes |
| `gemini` | _(planned)_ Cost-effective, 1M context | ✅ Yes |
| `openai` | _(planned)_ Enterprise standard | ✅ Yes |

Switch by setting one env variable. No code changes.

---

## 🏗️ Architecture

```
defect-pilot/
├── agent/
│   ├── jira_reader.py        # Fetches & parses Jira issues (ADF, URLs, attachments, links)
│   ├── defect_enricher.py    # AI enrichment — text + vision, completeness scoring
│   └── jira_updater.py       # Writes enriched data back to Jira (Sprint 4)
├── ai/
│   ├── base_provider.py      # Abstract base — add new providers in one file
│   ├── anthropic_provider.py # Claude (vision supported)
│   ├── ollama_provider.py    # Local LLM (vision: model-dependent)
│   └── provider_factory.py   # Instantiates provider from config
├── retest/
│   └── playwright_writer.py  # Generates flat Playwright retest scripts (Sprint 3)
├── db/
│   └── defect_store.py       # SQLite — local defect lifecycle tracking
├── config/
│   └── settings.py           # .env loader and validation
├── scripts/
│   └── run_enrichment.py     # CLI entry point — enrich a single issue
└── tests/
    ├── unit/                 # Unit tests, all mocked — no real Jira/AI calls
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
# Edit .env — Jira credentials + AI provider

# 4. Run enrichment
python scripts/run_enrichment.py --issue PROJ-123
python scripts/run_enrichment.py --issue PROJ-123 --debug
```

---

## ⚙️ Configuration

`.env` file:

```env
# AI Provider: "anthropic" or "ollama"
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

# Jira
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=your-token-here
JIRA_PROJECT_KEY=PROJ
```

> ⚠️ **Jira configuration variance:** Every Jira instance is configured differently.  
> Issue type names, link types, and custom fields vary per project and locale (PL/EN).  
> defect-pilot stores all values as raw strings — never hardcoded against specific names.  
> See [LEARNINGS.md](LEARNINGS.md) for the full variance table and design decisions.

---

## 🤖 AI provider notes

**Ollama (local):**
- Vision requires a vision-capable model — `llava` recommended, `llama3.2` is text-only
- `WinError 10061` = Ollama process not running — run `ollama serve` first
- Known limitation: llava occasionally hallucinates URLs or element names when data is missing — generated scripts mark AI-inferred selectors with `# TODO: verify`

**Anthropic (Claude):**
- Best output quality, especially for structured extraction and Polish/English bilingual reports
- Vision supported out of the box
- Data leaves your machine — check NDA / data residency before use

---

## 🗺️ Roadmap

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 0 | Repo scaffold, config, AI provider stubs | ✅ Done |
| Sprint 1 | Jira Reader — ADF parsing, attachments, comments, issue links | ✅ Done |
| Sprint 2 | AI Enricher — multimodal (text + vision), bilingual prompts, linked requirements | ✅ Done |
| Sprint 3 | Playwright Writer — flat retest script generation, Salesforce Shadow DOM | 🔄 In progress |
| Sprint 4 | Jira Updater — write enriched data + script back as Jira comment | ⏳ Planned |
| Sprint 5 | CLI, CI/CD, Allure reports, provider comparison, demo GIF | ⏳ Planned |

---

## 🧪 Test environment

UAT runs against:
- **Jira Cloud** — real instance (`STWA` project), synthetic defects reflecting real-world patterns
- **Salesforce Developer Edition** — free instance, UI automation including Lightning Web Components and Shadow DOM

---

## 📓 Project diary

See [LEARNINGS.md](LEARNINGS.md) for architectural decisions, lessons learned, dead ends, and honest notes from each sprint.

---

## 🤝 Contributing

PRs welcome. Open an issue first for major changes.

---

## 📄 License

MIT
