from datetime import datetime, timedelta, timezone
from decimal import Decimal

from psycopg import errors as pg_errors

from .errors import ApiError
from .schemas import BidCreate, RfqCreate

ONE_MIN = timedelta(minutes=1)


def utcnow():
    return datetime.now(timezone.utc)


def format_inr(amount):
    # indian digit grouping
    whole, frac = f"{Decimal(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        chunks = []
        while len(head) > 2:
            chunks.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join(([head] if head else []) + chunks + [tail])
    return f"₹{whole}.{frac}"


def get_status(auction_row, now):
    if now < auction_row["bid_start_at"]:
        return "UPCOMING"
    if now < auction_row["current_close_at"]:
        return "ACTIVE"
    if auction_row["current_close_at"] >= auction_row["forced_close_at"]:
        return "FORCE_CLOSED"
    return "CLOSED"


def write_log(conn, rfq_id, event_type, msg, when, bid_id=None, sup_id=None,
              old_close=None, new_close=None, reason=None):
    conn.execute(
        """
        INSERT INTO activity_logs
          (rfq_id, event_type, bid_id, supplier_id, old_close_at, new_close_at, reason, message, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (rfq_id, event_type, bid_id, sup_id, old_close, new_close, reason, msg, when),
    )


def push_status(conn, auction_row, now):
    # persist status change exactly once
    new_st = get_status(auction_row, now)
    if new_st == auction_row["status"]:
        return auction_row
    with conn.transaction():
        changed = conn.execute(
            "UPDATE rfqs SET status = %s WHERE id = %s AND status = %s",
            (new_st, auction_row["id"], auction_row["status"]),
        )
        if changed.rowcount == 1 and new_st in ("CLOSED", "FORCE_CLOSED"):
            event = "AUCTION_CLOSED" if new_st == "CLOSED" else "AUCTION_FORCE_CLOSED"
            text = "Auction closed" if new_st == "CLOSED" else "Auction force closed (forced close time reached)"
            write_log(conn, auction_row["id"], event, text, auction_row["current_close_at"])
    return {**auction_row, "status": new_st}


def sync_all_statuses(conn, now):
    for row in conn.execute("SELECT * FROM rfqs WHERE status IN ('UPCOMING', 'ACTIVE')").fetchall():
        push_status(conn, row, now)


RANK_SQL = """
SELECT best.*, ROW_NUMBER() OVER (ORDER BY best.total_amount, best.created_at, best.id) AS rank
FROM (
  SELECT DISTINCT ON (b.supplier_id) b.*, s.name AS carrier_name
  FROM bids b JOIN suppliers s ON s.id = b.supplier_id
  WHERE b.rfq_id = %s
  ORDER BY b.supplier_id, b.total_amount, b.created_at, b.id
) best
ORDER BY rank
"""


def get_rankings(conn, rfq_id):
    return conn.execute(RANK_SQL, (rfq_id,)).fetchall()


def check_trigger(auction_row, old_table, new_table, carrier):
    x_mins = auction_row["trigger_window_min"]
    ttype = auction_row["trigger_type"]

    if ttype == "BID_RECEIVED":
        return True, f"Bid received from {carrier} within the last {x_mins} min before close"

    if ttype == "ANY_RANK_CHANGE":
        old_ranks = {r["supplier_id"]: r["rank"] for r in old_table}
        changes = []
        for r in new_table:
            was = old_ranks.get(r["supplier_id"])
            if was != r["rank"]:
                old_label = f"L{was}" if was else "new"
                changes.append(f"{r['carrier_name']} {old_label}→L{r['rank']}")
        if changes:
            return True, f"Supplier ranking changed within the last {x_mins} min: {', '.join(changes)}"
        return False, None

    if ttype == "L1_CHANGE":
        old_l1 = old_table[0] if old_table else None
        new_l1 = new_table[0]
        old_sup_id = old_l1["supplier_id"] if old_l1 else None
        if old_sup_id != new_l1["supplier_id"]:
            old_name = old_l1["carrier_name"] if old_l1 else "none"
            return True, f"L1 changed within the last {x_mins} min: {old_name} → {new_l1['carrier_name']}"
        return False, None

    return False, None


def create_rfq(conn, data, now):
    errs = {}
    if data.bid_close_at <= data.bid_start_at:
        errs["bidCloseAt"] = "Bid close time must be after bid start time"
    elif data.bid_close_at <= now:
        errs["bidCloseAt"] = "Bid close time must be in the future"
    if data.forced_close_at <= data.bid_close_at:
        errs["forcedCloseAt"] = "Forced close time must be later than bid close time"
    if errs:
        raise ApiError(400, "Validation failed", errs)

    try:
        with conn.transaction():
            if data.reference_id:
                already_there = conn.execute(
                    "SELECT 1 FROM rfqs WHERE reference_id = %s", (data.reference_id,)
                ).fetchone()
                if already_there:
                    raise ApiError(409, "Validation failed", {"referenceId": "Reference ID already exists"})

            new_id = conn.execute("SELECT nextval(pg_get_serial_sequence('rfqs', 'id')) AS id").fetchone()["id"]
            ref = data.reference_id or f"RFQ-{new_id:05d}"
            new_rfq = conn.execute(
                """
                INSERT INTO rfqs (id, reference_id, name, pickup_date, bid_start_at, bid_close_at,
                                  current_close_at, forced_close_at, trigger_window_min, extension_min,
                                  trigger_type, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'UPCOMING', %s)
                RETURNING *
                """,
                (new_id, ref, data.name, data.pickup_date,
                 data.bid_start_at, data.bid_close_at, data.bid_close_at, data.forced_close_at,
                 data.trigger_window_minutes, data.extension_minutes, data.trigger_type.value, now),
            ).fetchone()
            write_log(conn, new_rfq["id"], "RFQ_CREATED", "RFQ created with British Auction enabled", now)
            return push_status(conn, new_rfq, now)
    except pg_errors.UniqueViolation:
        raise ApiError(409, "Validation failed", {"referenceId": "Reference ID already exists"}) from None


def submit_bid(conn, rfq_id, data, now):
    if data.quote_valid_until < now.date():
        raise ApiError(400, "Validation failed", {"quoteValidUntil": "Quote validity cannot be in the past"})
    total_price = data.total
    if total_price <= 0:
        raise ApiError(400, "Validation failed", {"freightCharges": "Total quote must be greater than 0"})

    with conn.transaction():
        # lock so concurrent bids on same auction go one at a time
        auction_row = conn.execute("SELECT * FROM rfqs WHERE id = %s FOR UPDATE", (rfq_id,)).fetchone()
        if not auction_row:
            raise ApiError(404, "RFQ not found")

        current_st = get_status(auction_row, now)
        if current_st == "UPCOMING":
            raise ApiError(409, "Auction has not started yet")
        if current_st != "ACTIVE":
            raise ApiError(409, "Auction is force closed" if current_st == "FORCE_CLOSED" else "Auction is closed")

        # upsert supplier (case-insensitive name)
        conn.execute(
            "INSERT INTO suppliers (name, created_at) VALUES (%s, %s) ON CONFLICT ((lower(name))) DO NOTHING",
            (data.carrier_name, now),
        )
        vendor = conn.execute(
            "SELECT * FROM suppliers WHERE lower(name) = lower(%s)", (data.carrier_name,)
        ).fetchone()

        old_table = get_rankings(conn, rfq_id)
        my_old_bid = next((r for r in old_table if r["supplier_id"] == vendor["id"]), None)
        if my_old_bid and total_price >= my_old_bid["total_amount"]:
            cur_price = format_inr(my_old_bid["total_amount"])
            raise ApiError(422, f"New quote must be lower than your current quote of {cur_price}",
                           {"freightCharges": f"Total must be below {cur_price}"})

        placed_bid_id = conn.execute(
            """
            INSERT INTO bids (rfq_id, supplier_id, freight_charges, origin_charges, destination_charges,
                              transit_time_days, quote_valid_until, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (rfq_id, vendor["id"], data.freight_charges, data.origin_charges, data.destination_charges,
             data.transit_time_days, data.quote_valid_until, now),
        ).fetchone()["id"]

        new_table = get_rankings(conn, rfq_id)
        rank_num = next(r["rank"] for r in new_table if r["supplier_id"] == vendor["id"])
        bid_msg = f"{vendor['name']} submitted {format_inr(total_price)} (L{rank_num})"

        # check trigger window
        ext_info = None
        note = None
        trigger_starts_at = auction_row["current_close_at"] - auction_row["trigger_window_min"] * ONE_MIN
        if now >= trigger_starts_at:
            should_extend, trigger_reason = check_trigger(auction_row, old_table, new_table, vendor["name"])
            if should_extend:
                would_be_close = auction_row["current_close_at"] + auction_row["extension_min"] * ONE_MIN
                actual_close = min(would_be_close, auction_row["forced_close_at"])
                if actual_close > auction_row["current_close_at"]:
                    ext_info = {
                        "old_close_at": auction_row["current_close_at"],
                        "new_close_at": actual_close,
                        "reason": trigger_reason,
                        "capped": actual_close < would_be_close,
                    }
                else:
                    note = "Extension trigger met, but forced close time already reached"

        write_log(conn, rfq_id, "BID_SUBMITTED",
                  bid_msg + (f" — {note.lower()}" if note else ""), now,
                  bid_id=placed_bid_id, sup_id=vendor["id"])

        if ext_info:
            conn.execute(
                "UPDATE rfqs SET current_close_at = %s, extension_count = extension_count + 1 WHERE id = %s",
                (ext_info["new_close_at"], rfq_id),
            )
            mins_added = (ext_info["new_close_at"] - ext_info["old_close_at"]) / ONE_MIN
            ext_msg = (
                f"Close time extended by {mins_added:g} min (capped at forced close time)"
                if ext_info["capped"]
                else f"Close time extended by {mins_added:g} min"
            )
            write_log(conn, rfq_id, "TIME_EXTENDED", ext_msg, now,
                      bid_id=placed_bid_id, sup_id=vendor["id"],
                      old_close=ext_info["old_close_at"], new_close=ext_info["new_close_at"],
                      reason=ext_info["reason"])

        auction_row = conn.execute("SELECT * FROM rfqs WHERE id = %s", (rfq_id,)).fetchone()
        push_status(conn, auction_row, now)

    return {"bid_id": placed_bid_id, "rank": rank_num, "extension": ext_info, "note": note}


LIST_SQL = """
SELECT r.*, st.bid_count, st.supplier_count, l1.total_amount AS lowest_amount, l1.carrier_name AS lowest_carrier
FROM rfqs r
CROSS JOIN LATERAL (
  SELECT COUNT(*) AS bid_count, COUNT(DISTINCT supplier_id) AS supplier_count FROM bids WHERE rfq_id = r.id
) st
LEFT JOIN LATERAL (
  SELECT b.total_amount, s.name AS carrier_name
  FROM bids b JOIN suppliers s ON s.id = b.supplier_id
  WHERE b.rfq_id = r.id
  ORDER BY b.total_amount, b.created_at, b.id
  LIMIT 1
) l1 ON TRUE
ORDER BY r.created_at DESC, r.id DESC
"""


def make_rfq_dict(row, now):
    return {
        "id": row["id"],
        "reference_id": row["reference_id"],
        "name": row["name"],
        "pickup_date": row["pickup_date"],
        "bid_start_at": row["bid_start_at"],
        "bid_close_at": row["bid_close_at"],
        "current_close_at": row["current_close_at"],
        "forced_close_at": row["forced_close_at"],
        "status": get_status(row, now),
        "extension_count": row["extension_count"],
        "config": {
            "trigger_window_minutes": row["trigger_window_min"],
            "extension_minutes": row["extension_min"],
            "trigger_type": row["trigger_type"],
        },
        "created_at": row["created_at"],
    }


def make_bid_dict(row):
    return {
        "id": row["id"],
        "supplier_id": row["supplier_id"],
        "carrier_name": row["carrier_name"],
        "freight_charges": float(row["freight_charges"]),
        "origin_charges": float(row["origin_charges"]),
        "destination_charges": float(row["destination_charges"]),
        "total_amount": float(row["total_amount"]),
        "transit_time_days": row["transit_time_days"],
        "quote_valid_until": row["quote_valid_until"],
        "created_at": row["created_at"],
    }


def list_rfqs(conn, now):
    sync_all_statuses(conn, now)
    all_rows = conn.execute(LIST_SQL).fetchall()
    result = []
    for row in all_rows:
        item = make_rfq_dict(row, now)
        item["bid_count"] = row["bid_count"]
        item["supplier_count"] = row["supplier_count"]
        if row["lowest_amount"] is None:
            item["lowest_bid"] = None
        else:
            item["lowest_bid"] = {"amount": float(row["lowest_amount"]), "carrier_name": row["lowest_carrier"]}
        result.append(item)
    return result


def get_rfq_detail(conn, rfq_id, now):
    rfq_row = conn.execute("SELECT * FROM rfqs WHERE id = %s", (rfq_id,)).fetchone()
    if not rfq_row:
        raise ApiError(404, "RFQ not found")
    rfq_row = push_status(conn, rfq_row, now)

    ranking_list = get_rankings(conn, rfq_id)
    best_bid_ids = {r["id"] for r in ranking_list}

    all_bids = conn.execute(
        """
        SELECT b.*, s.name AS carrier_name FROM bids b JOIN suppliers s ON s.id = b.supplier_id
        WHERE b.rfq_id = %s ORDER BY b.total_amount, b.created_at, b.id
        """,
        (rfq_id,),
    ).fetchall()

    logs = conn.execute(
        """
        SELECT a.*, s.name AS carrier_name FROM activity_logs a LEFT JOIN suppliers s ON s.id = a.supplier_id
        WHERE a.rfq_id = %s ORDER BY a.created_at, a.id
        """,
        (rfq_id,),
    ).fetchall()

    return {
        "rfq": make_rfq_dict(rfq_row, now),
        "rankings": [
            {**make_bid_dict(r), "rank": r["rank"], "label": f"L{r['rank']}"}
            for r in ranking_list
        ],
        "bids": [
            {**make_bid_dict(b), "is_current": b["id"] in best_bid_ids}
            for b in all_bids
        ],
        "activity": [
            {
                "id": a["id"],
                "event_type": a["event_type"],
                "message": a["message"],
                "reason": a["reason"],
                "bid_id": a["bid_id"],
                "carrier_name": a["carrier_name"],
                "old_close_at": a["old_close_at"],
                "new_close_at": a["new_close_at"],
                "created_at": a["created_at"],
            }
            for a in logs
        ],
    }
