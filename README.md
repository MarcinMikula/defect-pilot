# 🛩️ defect-pilot

> AI-powered bug reproduction & retest agent for QA engineers.  
> Reads Jira defects, enriches them with technical context, generates Playwright retest scripts — locally or via API.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Playwright](https://img.shields.io/badge/Playwright-latest-green)
![Jira](https://img.shields.io/badge/Jira-Cloud-blue)
![AI](https://img.shields.io/badge/AI-Ollama%20%7C%20Anthropic-purple)
![Tests](https://img.shields.io/badge/Tests-55%20passed-brightgreen)
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
identifies UI elements from screenshots, and generates an automated retest
script. Root cause analysis stays with the dev. Everything else gets automated.

---

## ✅ The solution

**defect-pilot** bridges that gap:

```
Jira defect (minimal)
    ↓
📥  JiraReader      — fetches issue, parses ADF, downloads screenshots
    ↓
🤖  DefectEnricher  — AI analyzes text + images, extracts structured context
    ↓
🎭  PlaywrightWriter — generates retest script (Sprint 3)
    ↓
📤  JiraUpdater     — enriched data + script written back to Jira (Sprint 4)
    ↓
💾  DefectStore     — local SQLite tracks defect lifecycle (Sprint 4)
```

### What AI extracts from a minimal defect report:

| Field | Source |
|-------|--------|
| Structured reproduction steps | Description text + screenshot |
| Expected vs actual result | Inferred from context |
| URL where bug occurred | Description or screenshot |
| UI elements & selectors | Screenshot analysis |
| Error message | Screenshot (vision) |
| Requirement references | e.g. `OPL-SF-008` found in description |
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
│   ├── jira_reader.py        # Reads & parses Jira issues (ADF, attachments, links)
│   ├── defect_enricher.py    # AI-powered enrichment (text + vision)
│   └── jira_updater.py       # Writes enriched data back to Jira
├── ai/
│   ├── base_provider.py      # Abstract base class — add new providers easily
│   ├── anthropic_provider.py # Claude (vision supported)
│   └── ollama_provider.py    # Local LLM (vision: model-dependent)
├── retest/
│   └── playwright_writer.py  # Generates Playwright retest scripts
├── db/
│   └── defect_store.py       # SQLite — local defect lifecycle tracking
├── config/
│   └── settings.py           # .env / YAML config loader
├── scripts/
│   └── test_live_stwa5.py    # Live integration test
└── tests/
    └── unit/                 # 55 tests, all mocked
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
# Edit .env — add Jira credentials + choose AI provider

# 4. Run (Sprint 5 — CLI coming)
python scripts/test_live_stwa5.py
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
# Prerequisites: install https://ollama.com + run: ollama pull llama3.2
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Jira
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=your-token-here
JIRA_PROJECT_KEY=PROJ
```

> ⚠️ **Jira configuration variance:** Every Jira instance is configured differently.  
> Issue type names, link types, and custom fields vary per project and locale (PL/EN).  
> defect-pilot handles this by storing all values as raw strings — never hardcoded.  
> See [LEARNINGS.md](LEARNINGS.md) for the full variance table.

---

## 🗺️ Roadmap

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 0 | Repo scaffold, config, AI provider stubs | ✅ Done |
| Sprint 1 | Jira Reader — ADF parsing, attachments, comments, issue links | ✅ Done |
| Sprint 2 | AI Enricher — multimodal (text + vision), bilingual prompts | ✅ Done |
| Sprint 3 | Playwright Writer — retest script generation, Shadow DOM (Salesforce) | 🔄 Next |
| Sprint 4 | DB + Jira Updater + Retest Scheduler | ⏳ Planned |
| Sprint 5 | CLI, CI/CD, Allure, provider comparison, demo GIF | ⏳ Planned |

---

## 🧪 Test environment

UAT runs against:
- **Jira Cloud** — real instance (`STWA` project), synthetic defects
- **Salesforce Developer Edition** — free instance, UI automation including Shadow DOM

---

## 📓 Project diary

See [LEARNINGS.md](LEARNINGS.md) for architectural decisions, lessons learned, and things that surprised us during development.

---

## 🤝 Contributing

PRs welcome. Open an issue first for major changes.

---

## 📄 License

MIT
