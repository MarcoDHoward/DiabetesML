# Prediction Market Scanner

Scan **Polymarket** and **Kalshi** for near-certain outcomes. Generates AI-powered research reports via Claude to help you verify high-probability markets independently.

**Runs on:** iPhone (Safari PWA), Windows (Chrome/Edge PWA), or any browser.

---

## What It Does

1. **Scans both platforms** every 15 minutes (configurable) for markets where YES probability ≥ 88%
2. **Cross-references** the same event appearing on both platforms side-by-side
3. **Generates research reports** using Claude — background, why the probability is high, key risks, and what to check independently

---

## Quick Start

### 1. Backend setup

```bash
cd backend
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and Kalshi credentials
pip install -r requirements.txt
uvicorn main:app --reload
```

### 2. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

App is now at `http://localhost:3000`

### 3. Docker (recommended for deployment)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env
docker compose up -d
```

---

## API Keys Needed

| Service | Required | Where to get |
|---|---|---|
| **Anthropic** | Yes (for reports) | [console.anthropic.com](https://console.anthropic.com) |
| **Kalshi** | Optional | [kalshi.com](https://kalshi.com) → Settings → API Keys |
| **Polymarket** | Not needed | Public read API, no auth |

### Kalshi RSA key setup

1. Create a free Kalshi account
2. Go to Settings → API Keys → Create Key
3. Download the private key as `kalshi_private_key.pem`
4. Place it in `backend/` and set `KALSHI_PRIVATE_KEY_PATH=./kalshi_private_key.pem` in `.env`

---

## iPhone Installation

1. Open `http://your-server-address:3000` in **Safari**
2. Tap the **Share** button → **Add to Home Screen**
3. The app installs like a native app

## Windows Installation

1. Open in **Chrome** or **Edge**
2. Look for the install icon in the address bar (or go to browser menu → Install app)
3. The app installs and appears in the Start menu

---

## Configuration

Edit `backend/.env`:

```env
ANTHROPIC_API_KEY=...
KALSHI_API_KEY_ID=...
KALSHI_PRIVATE_KEY_PATH=./kalshi_private_key.pem
PROBABILITY_THRESHOLD=0.88   # 88% minimum
SCAN_INTERVAL_MINUTES=15     # How often to scan
```

The threshold can also be adjusted in the app UI without restarting.

---

## Architecture

```
Browser/PWA (Next.js)
    ↕ REST API
FastAPI Backend
    ├── APScheduler → polls Polymarket + Kalshi every 15 min
    ├── Deduplicator → matches same event across platforms
    ├── SQLite DB → caches markets + reports
    └── Claude API → generates research reports on demand
```

---

## Deployment

For public access from your phone anywhere (not just local network), deploy to:
- **Railway** — `railway up` (free tier available)
- **Fly.io** — `fly launch`
- **Render** — connect GitHub repo

Set `NEXT_PUBLIC_API_URL` to your backend's public URL.
