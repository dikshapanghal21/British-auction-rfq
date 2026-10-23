# British Auction RFQ

This is an RFQ (Request for Quote) platform built around the British Auction model — where the clock doesn't just tick down but can actually extend itself when there's last-minute activity, keeping things competitive right until the end.

The core idea: shippers post freight RFQs, carriers submit quotes, and the system automatically nudges the close time whenever something interesting happens (a new bid, a rank change, etc.). You can configure how sensitive the auction is, how many times it can extend, and when it gets force-closed no matter what.

**Built with:** React on the frontend, Python + FastAPI on the backend, and PostgreSQL doing the heavy lifting for data.

| What | Where |
|---|---|
| Architecture + High Level Design | [docs/HLD.md](docs/HLD.md) |
| Database schema design | [docs/SCHEMA.md](docs/SCHEMA.md) and the actual DDL at [backend/app/schema.sql](backend/app/schema.sql) |
| Backend code | [backend/](backend) |
| Frontend code | [frontend/](frontend) |

---

## Before you start

You'll need these on your machine:

- **Python 3.10 or newer**
- **Node.js 20 or newer**
- **PostgreSQL 13 or newer** — either installed locally (grab it from postgresql.org; don't forget the password you set for the `postgres` user), or just use the Docker shortcut below:

```bash
docker compose up -d
```

That spins up a Postgres container with username `postgres` and password `postgres`. No fuss.

---

## Getting it running

You'll need two terminals open — one for the backend, one for the frontend.

### Terminal 1 — Backend

**On macOS / Linux:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # open .env and drop your Postgres password into DATABASE_URL
python -m app.seed            # optional, but nice — loads 6 demo auctions to play with
uvicorn app.main:app --reload --port 8000
```

**On Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # open .env and drop your Postgres password into DATABASE_URL
python -m app.seed            # optional, but nice — loads 6 demo auctions to play with
uvicorn app.main:app --reload --port 8000
```

The first time it starts, it'll create the `british_auction` database and set up all the tables automatically — nothing manual needed.

Once it's up, Swagger API docs are live at http://localhost:8000/docs if you want to poke around.

### Terminal 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173** in your browser. Vite is set up to proxy all `/api` calls straight to the FastAPI server on port 8000, so the two just work together.

---

## Running the tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

There are 24 tests in total, all running against a real PostgreSQL instance (same credentials as your `.env`, but it uses a separate `british_auction_test` database that's created automatically). They cover all 3 trigger types, the extension cap, force close behavior, ranking and tie-breaking logic, input validation, HTTP error formats, and a 30-thread concurrent bid test to make sure the row-level lock actually holds up under pressure.

---

## Try it out

The best way to get a feel for how things work:

1. Run `python -m app.seed`, then open http://localhost:5173

2. Click into **Mumbai → Delhi FTL** — it's seeded to already be inside its 10-minute trigger window. Submit a quote and watch the close time extend by 3 minutes. The activity log will tell you exactly why it extended. (Heads up: seed times are relative to when you run the seed script, so re-run it fresh before any demo.)

3. Click into **Ahmedabad → Jaipur** to see what a fully extended auction looks like — it was extended twice, hit the forced close cap, and got Force Closed.

4. Hit **+ New RFQ** to create your own and play with the X (extension duration), Y (trigger window), and trigger type settings.

---

## How the project is laid out

```
backend/
  app/schema.sql        tables, enums, constraints, indexes
  app/auction.py        the auction engine — ranking, triggers, extensions, status transitions, activity log
  app/schemas.py        Pydantic models for requests and responses
  app/routes.py         all the REST endpoints
  app/main.py           FastAPI app setup, error handlers, startup logic, background status sweeper
  app/db.py             connection pool, auto-creates the DB, applies the schema
  app/seed.py           demo data loader
  tests/                the full pytest suite (engine + API + concurrency tests)

frontend/src/
  pages/AuctionList.jsx     the main listing page
  pages/CreateRfq.jsx       the RFQ creation form
  pages/AuctionDetail.jsx   detail view — ranking, bid history, config, timeline
  components/BidForm.jsx    quote submission widget
  components/ActivityLog.jsx

docs/                   HLD, schema docs, diagrams (PNG exports + Graphviz .dot source)
docker-compose.yml      optional Postgres container if you don't want to install it locally
```

---

## A few design decisions worth knowing

- **Supplier identity is just the carrier name** (case-insensitive). There's no login or auth — that was intentionally out of scope.
- A supplier can only submit a quote that's **lower** than their current one. The ranking always uses each supplier's best (lowest) quote. If two suppliers are tied on price, the earlier bid wins.
- **Total price = freight + origin charges + destination charges** — this is a Postgres generated column, and all ranking is done on total.
- When an extension fires, Y minutes get added to the **current** close time (not the original). The trigger window shifts along with it.
- **Force Closed** means the auction ended because extensions hit their cap. **Closed** means it ended normally at its scheduled time.
- A brand new supplier entering the ranking counts as a rank change — so the trigger hierarchy is: bid received ⊇ rank change ⊇ L1 change.
- Concurrent bids on the same auction are serialized using `SELECT … FOR UPDATE` on the RFQ row, so there are no race conditions.

---

## Something not working?

| What you're seeing | What to do |
|---|---|
| `password authentication failed for user "postgres"` | Open `backend/.env` and make sure `DATABASE_URL` has your actual Postgres password in it |
| `connection refused` on port 5432 | Postgres isn't running — start the service, or run `docker compose up -d` |
| `running scripts is disabled on this system` (PowerShell venv activate) | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` in PowerShell, then try activating again |
| `python` command not found on Windows | Reinstall Python and make sure "Add python.exe to PATH" is checked, or try `py` instead of `python` |
| UI says "Could not load auctions" | The backend isn't running — make sure Terminal 1 is up and listening on port 8000 |
