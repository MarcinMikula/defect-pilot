# 🛩️ defect-pilot

> AI-powered bug reproduction & retest agent for QA engineers.  
> Reads Jira defects, enriches them with technical context, generates Playwright retest scripts — locally or via API.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Playwright](https://img.shields.io/badge/Playwright-latest-green)
![Jira](https://img.shields.io/badge/Jira-Cloud-blue)
![AI](https://img.shields.io/badge/AI-Ollama%20%7C%20Anthropic-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🧠 What is this?

Manual testers find bugs. They write tickets. Devs can't reproduce them. Retests take forever.

**defect-pilot** bridges that gap:

1. 📥 Reads a Jira defect (title, description, screenshots, steps)
2. 🔍 AI enriches it — adds HTTP requests, DOM selectors, reproduction steps
3. 🎭 Generates a Playwright retest script automatically
4. 📤 Updates the Jira ticket with enriched data
5. 💾 Tracks defect status in a local database

All without your bug data leaving the building — if you want it that way.

---

## 🔒 Privacy-first AI design

Many QA teams work under NDAs or data residency requirements. Jira tickets are documentation — they can't be sent to external APIs without consent.

defect-pilot solves this with a **pluggable AI provider**:

| Provider | When to use |
|----------|-------------|
| `ollama` | Air-gapped / NDA environments, local LLM (Llama3, Mistral, etc.) |
| `anthropic` | Cloud projects, best quality output |

Switch by setting one env variable. No code changes.

---

## 🏗️ Architecture

```
defect-pilot/
├── agent/
│   ├── jira_reader.py        # Reads & parses Jira issues
│   ├── defect_enricher.py    # AI-powered enrichment
│   └── jira_updater.py       # Writes enriched data back to Jira
├── ai/
│   ├── base_provider.py      # Abstract base class
│   ├── anthropic_provider.py # Claude (Anthropic API)
│   └── ollama_provider.py    # Local LLM via Ollama
├── retest/
│   └── playwright_writer.py  # Generates Playwright retest scripts
├── db/
│   └── defect_store.py       # SQLite — local defect tracking
├── config/
│   └── settings.py           # Env/YAML config loader
└── tests/
    ├── unit/
    └── integration/
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

# 4. Run
python -m defect_pilot --issue PROJ-123
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
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Jira
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=your-token-here
JIRA_PROJECT_KEY=PROJ
```

---

## 🗺️ Roadmap

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 0 | Repo scaffold, config, AI provider stubs | ✅ Done |
| Sprint 1 | Jira Reader — connect, parse, extract | ✅ Done |
| Sprint 2 | AI Enricher — prompt engineering, selectors | 🔄 In Progress |
| Sprint 3 | Playwright Writer — retest script generation, Shadow DOM | ⏳ Planned |
| Sprint 4 | DB + Jira Updater + Retest Scheduler | ⏳ Planned |
| Sprint 5 | CLI, CI/CD, Allure, field_mapping.yml, demo GIF | ⏳ Planned |

---

## 🧪 Test environment

UAT runs against:
- **Jira Cloud** — real instance, synthetic defects
- **Salesforce Developer Edition** — free instance, UI automation including Shadow DOM

---

## 🤝 Contributing

PRs welcome. Open an issue first for major changes.

---

## 📄 License

MIT
