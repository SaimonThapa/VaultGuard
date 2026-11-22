# VaultGuard

A password manager for CSC 327 (Secure Software Development), Group 5 "Team Iron".
One master password unlocks a vault of saved credentials. The credentials are encrypted at rest, so a stolen database file is unreadable without that password.

> **Status:** boilerplate only. The frontend and backend run and talk to each other. Vault features haven't been built yet.

| Layer    | Tech                                                         |
| -------- | ------------------------------------------------------------ |
| Frontend | React 19 (JavaScript), Vite, Tailwind CSS v4, Biome (lint + format) |
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2, Uvicorn                  |
| Database | SQLite (a local file in `backend/data/`, never committed)    |
| Checks   | Ruff (lint + format), Bandit (security static analysis), pytest |

---

## 1. Prerequisites

- **Node.js 24+** (includes npm). Check with `node -v`.
- **Python 3.12+**. Check with `python --version` (`python3` on macOS/Linux).
- **Git**

## 2. Get the code

```bash
git clone <repo-url> VaultGuard
cd VaultGuard
```

## 3. Backend setup (first time)

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment. **You need to do this in every new terminal** before running backend commands:

| OS / shell             | Command                          |
| ---------------------- | -------------------------------- |
| Windows PowerShell     | `.venv\Scripts\Activate.ps1`     |
| Windows Git Bash       | `source .venv/Scripts/activate`  |
| macOS / Linux          | `source .venv/bin/activate`      |

> If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

Then install the dependencies and create your local env file:

```bash
pip install -r requirements-dev.txt
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

`.env` is git-ignored. Never commit it, and never put real passwords or keys in it.

## 4. Frontend setup (first time)

```bash
cd frontend
npm install
```

## 5. Run the app

Use two terminals.

**Terminal 1: backend** (from `backend/`, venv activated)

```bash
uvicorn app.main:app --reload --env-file .env
```

The API runs at http://127.0.0.1:8000. You can check it at http://127.0.0.1:8000/api/health.

**Terminal 2: frontend** (from `frontend/`)

```bash
npm run dev
```

Open http://localhost:5173. The page should say **`api: ok, db: ok`**. If it says `backend unreachable`, the backend isn't running.

In development, Vite proxies every `/api/*` request to the backend, so the frontend always calls relative URLs like `fetch("/api/...")`. Don't hardcode `http://127.0.0.1:8000` in frontend code.

**API docs:** set `DEBUG=true` in `backend/.env` and restart. The docs are then at http://127.0.0.1:8000/docs. They're off by default so the API surface isn't exposed.

## 6. Lint, format, test (run before pushing)

**Backend** (from `backend/`, venv activated):

```bash
ruff format .                          # auto-format
ruff check .                           # lint (includes security rules)
bandit -c pyproject.toml -r app        # SAST security scan
pytest                                 # tests
```

**Frontend** (from `frontend/`):

```bash
npm run check     # Biome: lint + format + sort imports, applies safe fixes
npm run lint      # lint only
npm run build     # production build, catches build errors
```

Tip: install the **Biome** and **Ruff** VS Code extensions to format on save.

## 7. Project structure

```
VaultGuard/
├─ backend/
│  ├─ app/
│  │  ├─ main.py          # FastAPI app, CORS, routes
│  │  ├─ config.py        # settings read from environment variables
│  │  └─ db.py            # SQLAlchemy engine/session, get_db dependency
│  ├─ tests/              # pytest tests
│  ├─ requirements.txt    # runtime deps (pinned)
│  ├─ requirements-dev.txt# + test/lint/SAST tools
│  ├─ pyproject.toml      # ruff / bandit / pytest config
│  └─ .env.example        # copy to .env
├─ frontend/
│  ├─ src/                # React app (App.jsx, main.jsx, index.css)
│  ├─ vite.config.js      # Tailwind plugin + /api proxy
│  └─ biome.json          # lint/format rules
└─ docs/                  # local-only planning docs (git-ignored, shared manually)
```

## 8. Environment variables (`backend/.env`)

| Variable          | Default                          | Purpose                                     |
| ----------------- | -------------------------------- | ------------------------------------------- |
| `FRONTEND_ORIGIN` | `http://localhost:5173`          | The only origin CORS allows                 |
| `DATABASE_URL`    | `sqlite:///./data/vaultguard.db` | SQLite file path (relative to `backend/`)   |
| `DEBUG`           | `false`                          | Enables `/docs`. Keep `false` outside dev   |

## 9. Test accounts and demo data

_To be added once vault features exist. Only fictional data will go here._

## 10. Team rules

- No real credentials, API keys, or personal data in code, commits, screenshots, or AI prompts.
- Pin new dependencies to exact versions in `requirements*.txt` or `package.json`.
- Run the checks in section 6 before pushing.

## Troubleshooting

- **`backend unreachable` on the page:** start the backend (step 5), and check that port 8000 is free.
- **`ModuleNotFoundError: app`:** run `uvicorn` from inside `backend/`, not the repo root.
- **`uvicorn`/`pytest` not found:** the venv isn't activated (step 3).
- **Port 5173 in use:** Vite picks another port. Set `FRONTEND_ORIGIN` in `.env` to match, or CORS will block requests that don't go through the proxy.
