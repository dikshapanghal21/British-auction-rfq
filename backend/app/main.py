import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .auction import sync_all_statuses, utcnow
from .db import apply_schema, create_pool, ensure_database
from .errors import ApiError
from .routes import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("auction")


async def sweeper_loop(pool):
    # background task: flip ACTIVE -> CLOSED/FORCE_CLOSED automatically
    while True:
        try:
            def do_sweep():
                with pool.connection() as conn:
                    sync_all_statuses(conn, utcnow())
            await asyncio.to_thread(do_sweep)
        except Exception:
            log.exception("status sweep failed")
        await asyncio.sleep(config.SWEEP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_database(config.DATABASE_URL)
    pool = create_pool(config.DATABASE_URL)
    with pool.connection() as conn:
        apply_schema(conn)
    app.state.pool = pool
    sweeper = asyncio.create_task(sweeper_loop(pool)) if config.SWEEPER_ENABLED else None
    yield
    if sweeper:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper
    pool.close()


app = FastAPI(title="British Auction RFQ API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")


@app.get("/api/health", tags=["Health"])
def health():
    return {"ok": True}


FIELD_MESSAGES = {
    "name": "RFQ name is required (max 200 characters)",
    "referenceId": "Reference ID: 2-40 chars, letters, digits, - or _",
    "pickupDate": "Valid pickup / service date is required",
    "bidStartAt": "Valid bid start date & time is required",
    "bidCloseAt": "Valid bid close date & time is required",
    "forcedCloseAt": "Valid forced close date & time is required",
    "triggerWindowMinutes": "Trigger window (X) must be a whole number between 1 and 1440",
    "extensionMinutes": "Extension duration (Y) must be a whole number between 1 and 1440",
    "triggerType": "Trigger must be one of BID_RECEIVED, ANY_RANK_CHANGE, L1_CHANGE",
    "carrierName": "Carrier name is required (max 100 characters)",
    "freightCharges": "Freight charges must be a number >= 0 (max 2 decimals)",
    "originCharges": "Origin charges must be a number >= 0 (max 2 decimals)",
    "destinationCharges": "Destination charges must be a number >= 0 (max 2 decimals)",
    "transitTimeDays": "Transit time must be a whole number of days (1-365)",
    "quoteValidUntil": "Valid quote validity date is required",
}


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content={"error": exc.message, "details": exc.details})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = {}
    for err in exc.errors():
        loc = err.get("loc", ())
        if loc and loc[0] == "path":
            return JSONResponse(status_code=404, content={"error": "RFQ not found"})
        if err.get("type") == "json_invalid":
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})
        field = str(loc[1]) if len(loc) > 1 else "body"
        details.setdefault(field, FIELD_MESSAGES.get(field, err.get("msg", "Invalid value")))
    return JSONResponse(status_code=400, content={"error": "Validation failed", "details": details})
