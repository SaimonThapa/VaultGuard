# VaultGuard

A password manager for CSC 327 (Secure Software Development), Group 5 "Team Iron".
Each user signs in with an account password, then unlocks their vault with a separate master key. Saved credentials are encrypted at rest (Argon2id + AES-256-GCM), so a stolen database file is unreadable without the master key.

> **Status:** complete. Sign up with email verification, an encrypted vault, a vault-health dashboard, import/export, an activity log, and recovery flows. All planned security demos have tests (section 6).

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

**Generate two secrets** (the app refuses to start while `JWT_SECRET` and `OTP_PEPPER` are still the placeholders):

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run it twice and paste one value after `JWT_SECRET=` and the other after `OTP_PEPPER=` in `backend/.env`.

**Email codes:** no mail server is needed. Verification and reset codes are printed in the backend terminal as `[EMAIL] ... code: 123456`. (Set the `SMTP_*` variables to send real email.)

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

Run a **single worker** (don't add `--workers`): unlocked vault keys are held in that process's memory. The API runs at http://127.0.0.1:8000. You can check it at http://127.0.0.1:8000/api/health.

**Terminal 2: frontend** (from `frontend/`)

```bash
npm run dev
```

Open http://localhost:5173. You'll see the dashboard as a visitor; sign up (or use a test account from section 9) to start. If requests fail, the backend isn't running.

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

**Run one security demo at a time** (from `backend/`):

```bash
pytest -v tests/test_tamper.py          # Demo 1: tamper detection (A04)
pytest -v tests/test_access_control.py  # Demo 2: broken access control (A01)
pytest -v tests/test_idor.py            # Demo 3: IDOR (A01)
pytest -v tests/test_sqli.py            # Demo 4: SQL injection (A05)
pytest -v tests/test_lockout.py         # Spare: brute-force lockout (A07)
```

Tip: install the **Biome** and **Ruff** VS Code extensions to format on save.

## 7. Project structure

```
VaultGuard/
├─ backend/
│  ├─ app/
│  │  ├─ main.py, config.py, db.py, errors.py, dependencies.py
│  │  ├─ routes/        # thin: URL in, controller call, JSON out
│  │  ├─ controllers/   # the actual logic (auth, vault, entries, health, transfer, account)
│  │  ├─ models/        # SQLAlchemy tables + request schemas
│  │  ├─ core/          # security building blocks: crypto, tokens, key_store, passwords
│  │  └─ services/      # outside world: email, HIBP
│  ├─ scripts/          # reset_db, show_db, tamper_entry (demo helpers)
│  ├─ tests/            # pytest: one file per security control and flow
│  ├─ requirements*.txt # pinned dependencies
│  └─ .env.example      # copy to .env
├─ frontend/
│  ├─ src/              # pages, components, context (auth, toasts, health), lib (api client)
│  ├─ vite.config.js    # Tailwind plugin + /api proxy
│  └─ biome.json        # lint/format rules
└─ docs/                # local-only planning docs (git-ignored, shared manually)
```

## 8. Environment variables (`backend/.env`)

| Variable | Default | Purpose |
| --- | --- | --- |
| `JWT_SECRET`, `OTP_PEPPER` | *(required)* | 32+ random characters each. The app won't start with placeholders |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | The only origin CORS allows |
| `DATABASE_URL` | `sqlite:///./data/vaultguard.db` | SQLite file path (relative to `backend/`) |
| `DEBUG` | `false` | Enables `/docs`. Keep `false` outside dev |
| `COOKIE_SECURE` | `false` | `true` when served over HTTPS |
| `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS`, `VAULT_IDLE_MINUTES` | `10`, `7`, `10` | Session lifetimes and vault auto-lock |
| `MAX_FAILED_ATTEMPTS`, `LOCKOUT_MINUTES` | `5`, `15` | Login and unlock lockout |
| `OTP_TTL_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_SECONDS` | `10`, `5`, `60` | Email code rules |
| `ARGON2_*` | `3`, `65536`, `4` | Argon2id cost for the master key |
| `HIBP_ENABLED` | `true` | Breach check via Have I Been Pwned (only a 5-character hash prefix is sent). `false` for offline demos |
| `SMTP_*` | *(unset)* | Optional real email; otherwise codes print to the log |

All variables are listed with defaults in `backend/.env.example`.

## 9. Test accounts and demo data

Load the demo data (stop the backend first; this **deletes** the local database). From `backend/` with the venv active:

```bash
python -m scripts.reset_db
```

It prints each account's recovery key. Everything is fictional.

| Account | Account password | Master key | Notes |
| --- | --- | --- | --- |
| `alice` | `Alice-Demo-Passphrase-2026!` | `7K3Q-9XWM-2PDA-H8RT-Y4NC-6VBE-1Z` | 12 entries: 2 weak, 1 reused pair, 1 overdue rotation, so the dashboard has findings |
| `bob` | `Bob-Demo-Passphrase-2026!` | `Bobs-Demo-Master-Key-2026-Orbit!` | 3 entries. The victim in the IDOR demo |

### Demo walkthroughs

1. **Tamper detection (Demo 1).** Log in as alice and unlock; note the score on the dashboard. In another terminal run `python -m scripts.show_db` to copy an entry id (this also shows that the stolen database is only ciphertext). Then `python -m scripts.tamper_entry <entry_id>`, and in the app press **Re-run** on the dashboard. The entry is flagged, the score drops to 40 or less, and opening it shows "failed its integrity check". `pytest -v tests/test_tamper.py` proves the same thing.
2. **Broken access control (Demo 2).** `pytest -v tests/test_access_control.py`. It walks every API route without a token, with an expired, forged or `alg=none` token, with a locked vault, and after the idle timeout.
3. **IDOR (Demo 3).** `pytest -v tests/test_idor.py`. alice uses bob's real entry id and gets a 404; bob's data is unchanged.
4. **SQL injection (Demo 4).** `pytest -v tests/test_sqli.py`. Payloads like `' OR 1=1 --` in search and login do nothing.

## 10. Team rules

- No real credentials, API keys, or personal data in code, commits, screenshots, or AI prompts.
- Pin new dependencies to exact versions in `requirements*.txt` or `package.json`.
- Run the checks in section 6 before pushing.

## Troubleshooting

- **The page can't reach the API:** start the backend (step 5), and check that port 8000 is free.
- **`ModuleNotFoundError: app`:** run `uvicorn` from inside `backend/`, not the repo root.
- **`RuntimeError: JWT_SECRET must be set`:** generate the two secrets in step 3.
- **`uvicorn`/`pytest` not found:** the venv isn't activated (step 3).
- **Port 5173 in use:** Vite picks another port. Set `FRONTEND_ORIGIN` in `.env` to match, or CORS will block requests that don't go through the proxy.
