# ReturnFlow — Order Returns & Refund Case Manager

A full-stack demonstration application for managing retail return requests, order validation, warehouse inspection, manager decisions, replacement dispatch and manually recorded refunds.

## Technology
- React 18 + Vite frontend
- Python Flask REST API
- SQLite database
- Recharts analytics
- Session-based authentication and role-based permissions

## Requirements
- Python 3.10+
- Node.js 18+ and npm

## Run with Docker

From the project root (the folder containing `docker-compose.yml`):

```bash
docker compose up --build
```

Open `http://localhost:5173`. The API is available at `http://localhost:5000`.

To stop the containers:

```bash
docker compose down
```

The SQLite file in `backend/returns.db` is mounted into the backend container, so application data persists across restarts.

## Deploy to Vercel

Vercel can host the Vite frontend. The Flask API needs to be deployed separately to a Python host, and SQLite needs persistent storage; do not rely on Vercel's serverless filesystem for the database.

1. Push this project to a GitHub repository.
2. In Vercel, import the repository and set **Root Directory** to `frontend`.
3. Use `npm run build` for **Build Command** and `dist` for **Output Directory**.
4. Add the environment variable `VITE_API_URL` to the Vercel project, with the deployed API base URL, for example `https://your-api-host.example.com/api` (no trailing slash). Redeploy after setting it.
5. On the backend host, set `SECRET_KEY` to a strong random value, `FRONTEND_ORIGIN` to your exact Vercel site origin (for example `https://your-app.vercel.app`), `SESSION_COOKIE_SAMESITE` to `None`, and `SESSION_COOKIE_SECURE` to `true`. Ensure the backend host preserves `backend/returns.db` on persistent storage.

The Vercel URL will only work once the separately hosted API is running and configured. The demo credentials and orders are intended for local/demo use, not a public production deployment.

## Run locally

### 1. Start the backend
Open a terminal in the `backend` folder:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The API runs at `http://localhost:5000`. The SQLite database (`returns.db`) is created automatically on first start and populated with demo users and sample orders.

### 2. Start the frontend
Open a second terminal in the `frontend` folder:

```bash
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://localhost:5173`.

## Demo logins

| Role | Email | Password |
|---|---|---|
| Customer Support Agent | support@demo.com | Support@123 |
| Warehouse Inspector | warehouse@demo.com | Warehouse@123 |
| Finance Officer | finance@demo.com | Finance@123 |
| Returns Manager | manager@demo.com | Manager@123 |

## Sample order references

- `ORD-2026-1001` — Olivia Carter — Wireless Headphones — ₹3,499
- `ORD-2026-1002` — Noah Wilson — Smart Watch — ₹5,999
- `ORD-2026-1003` — Ava Johnson — Bluetooth Speaker — ₹2,499
- `ORD-2026-1004` — Liam Brown — Mechanical Keyboard — ₹4,299
- `ORD-2026-1005` — Sophia Davis — USB-C Hub — ₹1,899
- `ORD-2026-1006` — Ethan Miller — Fitness Band — ₹2,199

## Main workflow

1. Sign in as Customer Support or Returns Manager and create a return using a valid order reference.
2. Sign in as Warehouse Inspector and open the case to record Pass, Fail or Needs Review plus inspection notes.
3. Sign in as Returns Manager to approve/reject the case. Approved cases must be assigned a Refund or Replacement resolution.
4. For Refund, sign in as Finance Officer (or Returns Manager) and record the amount and manual reference. This updates the case only; it does not transfer money.
5. For Replacement, sign in as Warehouse Inspector (or Returns Manager) and record the tracking reference.
6. A Returns Manager can close rejected, refunded or replacement-shipped cases.

## Notes / limitations
- This is a local academic/demo application, not a production deployment.
- No payment gateway is integrated. A refund entry records a manual refund reference only.
- Demo orders are seeded into SQLite. No real customer or payment data is used.
- For production, set a strong `SECRET_KEY`, configure HTTPS and trusted frontend origins, add CSRF protection, rate limiting, audit retention policies, backups and deployment-grade database hosting.
- The UI loads Google Fonts from Google Fonts; if offline, it falls back to local sans-serif fonts.

## API overview
- `POST /api/login`, `POST /api/logout`, `GET /api/me`
- `GET /api/orders`, `GET /api/orders/<order_ref>`
- `POST /api/returns`, `GET /api/returns`, `GET /api/returns/<id>`
- `POST /api/returns/<id>/inspect`
- `POST /api/returns/<id>/decision`
- `POST /api/returns/<id>/refund`
- `POST /api/returns/<id>/replacement`
- `POST /api/returns/<id>/close`
- `GET /api/analytics`

## Project structure

```text
order-returns-refund-manager/
├── backend/
│   ├── app.py
│   ├── init_db.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       └── style.css
└── README.md
```
