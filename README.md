# AI Operations Assistant

A **Multi-Agent AI System** that accepts natural-language tasks, plans execution steps, calls real APIs, and returns structured answers.

## Quick Start (One Command)

```bash
# After setup, run with:
uvicorn main:app --reload
```

Then open: **http://localhost:8000/docs**

---

## Setup Instructions

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/ai-ops-assistant.git
cd ai-ops-assistant
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
GEMINI_API_KEY=your_gemini_api_key
OPENWEATHERMAP_API_KEY=your_openweathermap_key
NEWSAPI_KEY=your_newsapi_key
GITHUB_TOKEN=optional_github_token
```

**Get API Keys:**
- Gemini: https://aistudio.google.com/app/apikey
- OpenWeatherMap: https://openweathermap.org/api
- NewsAPI: https://newsapi.org/register

### 3. Run the Application

```bash
uvicorn main:app --reload
```

Open: **http://localhost:8000/docs**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│   │   PLANNER    │→ │   EXECUTOR   │→ │   VERIFIER   │          │
│   │   Agent      │  │   Agent      │  │   Agent      │          │
│   └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                             ↓
         ┌──────────────────────────────────────┐
         │            TOOL REGISTRY             │
         │  ┌────────┐ ┌────────┐ ┌────────┐    │
         │  │ GitHub │ │Weather │ │  News  │    │
         │  └────────┘ └────────┘ └────────┘    │
         └──────────────────────────────────────┘
```

### Multi-Agent Design

| Agent | Role | Output |
|-------|------|--------|
| **Planner** | Converts natural language → JSON execution plan | `ExecutionPlan` with steps |
| **Executor** | Calls tools/APIs based on plan | `StepResult` for each step |
| **Verifier** | Validates results, formats final output | `FinalOutput` with summary |

### LLM Integration
- **Model**: Google Gemini 2.0 Flash
- **Structured Outputs**: Pydantic models for type-safe JSON responses
- **Prompts**: Agent-specific system prompts with JSON schema constraints

---

## Integrated APIs

| API | Purpose | Actions |
|-----|---------|---------|
| **GitHub API** | Repository search, user info | `search_repositories`, `get_repository`, `get_user` |
| **OpenWeatherMap API** | Weather data | `get_current_weather`, `get_forecast` |
| **NewsAPI** | News headlines, search | `get_top_headlines`, `search_news` |

---

## Example Prompts to Test

Try these in the Swagger UI (`POST /api/v1/task`):

```json
{"task": "Get the current weather in London"}
```

```json
{"task": "Find top 5 Python machine learning repositories on GitHub"}
```

```json
{"task": "Get the latest technology news headlines"}
```

```json
{"task": "What is the weather in Tokyo and show me trending AI repositories"}
```

```json
{"task": "Search for news about artificial intelligence"}
```

---

## Alternative Run Methods

### CLI Interface
```bash
python cli.py run "Get weather in Mumbai"
python cli.py tools  # List available tools
python cli.py interactive  # Interactive mode
```

### Streamlit Web UI
```bash
streamlit run ui/streamlit_app.py
```

---

## Project Structure

```
ai_ops_assistant/
├── agents/
│   ├── base.py          # Base agent class
│   ├── planner.py       # NL → JSON plan
│   ├── executor.py      # Call tools
│   ├── verifier.py      # Validate & format
│   └── orchestrator.py  # Coordinate workflow
├── tools/
│   ├── base.py          # Tool interface
│   ├── registry.py      # Tool discovery
│   ├── github_tool.py   # GitHub API
│   ├── weather_tool.py  # OpenWeatherMap
│   └── news_tool.py     # NewsAPI
├── llm/
│   ├── client.py        # Gemini client
│   ├── schemas.py       # Pydantic models
│   └── prompts.py       # Agent prompts
├── api/
│   ├── routes.py        # FastAPI endpoints
│   └── models.py        # API models
├── main.py              # Entry point
├── config.py            # Settings
└── requirements.txt
```

---

## Known Limitations & Tradeoffs

1. **Gemini Free Tier Limits**: The free tier has daily request limits (~1500/day). If exceeded, wait 24 hours or use a different API key.

2. **Sequential Execution**: Tool calls are executed sequentially, not in parallel. This ensures dependency handling but may be slower for independent steps.

3. **No Persistent Storage**: Task results are stored in-memory. Restarting the server clears history.

4. **API Rate Limits**: External APIs (GitHub, Weather, News) have their own rate limits. Caching is implemented to reduce redundant calls.

5. **English Only**: The system is optimized for English language tasks.

---

## Requirements Met

| Requirement | Status |
|-------------|--------|
| Multi-agent design (Planner, Executor, Verifier) | ✅ |
| LLM with structured outputs | ✅ Gemini + Pydantic |
| At least 2 real third-party APIs | ✅ 3 APIs (GitHub, Weather, News) |
| End-to-end result | ✅ |
| No hardcoded responses | ✅ All dynamic |
| Runs with one command | ✅ `uvicorn main:app` |

---

## License

MIT License
