# Synapse

> Where curiosity meets intelligence.

Synapse is an AI-powered chat application that lets you search for people, get weather updates, generate PDF profile reports, and have natural conversations — all through a single chat interface.

---

## Features

- **AI Chat** — Conversational answers on any topic using OpenAI or Google Gemini
- **Person Search** — Detailed profiles with bio, career, social media, and news
- **PDF Generation** — Download a structured PDF report for any person
- **Email PDF** — Send generated PDF reports via email (Mailgun)
- **Weather** — Real-time weather information for any city
- **LLM Switching** — Switch between OpenAI and Gemini at runtime; your choice persists across restarts
- **Search History** — All searches within a day are grouped into one session

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Svelte 4, Vite, Tailwind CSS |
| Backend | FastAPI, Python 3.11+ |
| LLM | OpenAI GPT-4o-mini / Google Gemini |
| Database | MongoDB (search history + profiles) |
| Cache | Redis (person profile cache) |
| PDF | ReportLab |
| Email | Mailgun |

---

## Project Structure

```
synapse/
├── backend/
│   ├── main.py                     # FastAPI app & all endpoints
│   ├── models.py                   # Pydantic models
│   ├── logger_config.py            # Logging setup
│   ├── requirements.txt
│   ├── .env                        # Environment variables (not committed)
│   ├── data/
│   │   ├── history.json            # Search history (auto-generated)
│   │   └── settings.json           # User preferences (auto-generated)
│   └── services/
│       ├── ai_service.py           # Person profile fetching via LLM
│       ├── email_service.py        # Mailgun email integration
│       ├── pdf_service.py          # PDF generation with ReportLab
│       └── llm/
│           ├── llm_service.py      # Provider manager
│           ├── openai_provider.py  # OpenAI integration
│           └── gemini_provider.py  # Gemini integration
└── frontend/
    ├── src/
    │   ├── App.svelte              # Main app
    │   ├── components/
    │   │   ├── SearchBox.svelte    # Chat input
    │   │   ├── SearchBar.svelte    # Landing search bar
    │   │   └── PersonCard.svelte   # Person profile card
    │   └── global.css
    ├── index.html
    ├── vite.config.js
    └── package.json
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+

### 1. Clone the repository

```bash
git clone https://github.com/your-username/synapse.git
cd synapse
```

### 2. Backend setup

```bash
cd backend
python -m venv env

# Linux/Mac
source env/bin/activate

# Windows
env\Scripts\activate

pip install -r requirements.txt
```

Create `backend/.env`:

```env
# LLM Provider
LLM_PROVIDER=gemini
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
GEMINI_API_KEY=your_gemini_key

# Authentication
API_BEARER_TOKEN=your_secret_token

# Email (Mailgun)
MAILGUN_API_KEY=your_mailgun_key
MAILGUN_DOMAIN=your_mailgun_domain
EMAIL_FROM=Synapse <you@example.com>

# External APIs
NEWS_API_KEY=your_newsapi_key
SERPAPI_API_KEY=your_serpapi_key
OPENWEATHERMAP_API_KEY=your_openweathermap_key

# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=synapse

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_CACHE_TTL=86400
```

Start the backend:

```bash
uvicorn main:app --reload --port 8000
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_BEARER_TOKEN=your_secret_token
```

Start the frontend:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat` | Main chat endpoint |
| GET | `/history` | Search history grouped by day |
| DELETE | `/history` | Clear all history |
| POST | `/person/pdf` | Generate person PDF (base64) |
| GET | `/person/pdf/download` | Download person PDF file |
| POST | `/email-pdf` | Email a person PDF |
| GET | `/llm/provider/status` | Current LLM provider info |
| POST | `/llm/provider/switch` | Switch LLM provider |
| GET | `/health` | Health check |
| GET | `/docs` | Interactive API docs (Swagger) |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | Yes | `openai` or `gemini` |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `GEMINI_API_KEY` | If using Gemini | Google Gemini API key |
| `API_BEARER_TOKEN` | Yes | Bearer token for all protected endpoints |
| `MAILGUN_API_KEY` | For email | Mailgun API key |
| `MAILGUN_DOMAIN` | For email | Mailgun sending domain |
| `EMAIL_FROM` | For email | Sender display name and address |
| `NEWS_API_KEY` | For news | NewsAPI.org key |
| `SERPAPI_API_KEY` | For search | SerpAPI key |
| `OPENWEATHERMAP_API_KEY` | For weather | OpenWeatherMap API key |

---

## License

MIT
