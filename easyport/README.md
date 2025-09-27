# EasyPort (Flask)

EasyPort is a lightweight ride‑hailing fare and ETA comparison app built with Flask. It lets you enter a source and destination, then compares options across multiple providers (e.g., Uber, Ola, Rapido, InDrive, Meru) in a single, consistent view.

Why this is needed

- Comparing rides today often means app‑hopping, inconsistent pricing models, and unclear ETAs.
- Surge pricing and availability vary by provider, making quick, informed decisions difficult.
- Developers and teams prototyping mobility use‑cases need a simple aggregation reference that runs locally without credentials.

Project purpose

- Provide a minimal, developer‑friendly reference for a ride aggregator: plain Flask backend + simple HTML/CSS frontend.
- Work out of the box using realistic mock data, with an opt‑in path to real provider integrations via a feature flag.
- Normalize provider responses to a unified schema the UI can render consistently.
- Serve as a learning scaffold for auth, persistence, and future provider OAuth/API integrations.

## Run

1. Create and activate venv (Windows PowerShell):

```bash
python -m venv .venv
.venv\\Scripts\\Activate.ps1
```

1. Install deps:

```bash
pip install -r requirements.txt
```

1. Start server:

```bash
python app.py
```

1. Open `http://localhost:5000`

Optional `.env`:

```env
PORT=5000
PROVIDER_API_ENABLED=false
UBER_CLIENT_ID=
UBER_CLIENT_SECRET=
UBER_REDIRECT_URI=
OLA_API_KEY=
RAPIDO_API_KEY=
INDRIVE_API_KEY=
MERU_API_KEY=
```

## API

- GET `/api/health` → `{ status: "OK", timestamp: "..." }`
- POST `/api/rides` with JSON `{ source, destination, passengers }` → mock ride options

## Notes

- This version removes Node/React. The UI is plain HTML/CSS/JS in `templates/` and `static/`.

## Provider Integrations (official)

Set `PROVIDER_API_ENABLED=true` after you have credentials and approvals. The server will:

- Geocode addresses with OpenStreetMap Nominatim
- Call each provider client in parallel (placeholders in `app.py`)
- Normalize responses to a unified schema expected by the frontend
- Fallback to mock data if providers are unavailable

You will need to implement OAuth/keys per provider in the placeholder functions and store secrets via environment variables.
