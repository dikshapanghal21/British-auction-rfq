"""
Load demo auctions:  python -m app.seed

Times are relative to now so bid windows are always fresh when you run it.
"""
from datetime import timedelta

from . import config
from .auction import create_rfq, submit_bid, sync_all_statuses, utcnow
from .db import apply_schema, connect, ensure_database
from .schemas import BidCreate, RfqCreate

NOW = utcnow()


def mins(n):
    return NOW + timedelta(minutes=n)


def days_from_now(n):
    return (NOW + timedelta(days=n)).date()


def make_quote(carrier, freight, origin, dest, transit=3):
    return BidCreate(
        carrier_name=carrier,
        freight_charges=freight,
        origin_charges=origin,
        destination_charges=dest,
        transit_time_days=transit,
        quote_valid_until=days_from_now(30),
    )


def seed_auction(conn, created_at, bids_list, **cfg):
    rfq = create_rfq(conn, RfqCreate(**cfg), created_at)
    for bid_time, bid_data in bids_list:
        submit_bid(conn, rfq["id"], bid_data, bid_time)


def main():
    ensure_database(config.DATABASE_URL)
    with connect(config.DATABASE_URL) as conn:
        apply_schema(conn)
        conn.execute("TRUNCATE activity_logs, bids, suppliers, rfqs RESTART IDENTITY CASCADE")

        # 1. Active, inside trigger window right now -> any bid extends it
        seed_auction(conn, mins(-30), [
            (mins(-20), make_quote("Blue Dart Cargo", 82000, 4000, 3500, 3)),
            (mins(-15), make_quote("Gati Logistics", 79500, 3800, 3500, 4)),
            (mins(-12), make_quote("VRL Logistics", 81000, 3000, 3000, 3)),
        ], name="Mumbai → Delhi FTL, 20 MT steel coils", reference_id="RFQ-DEMO-01",
            pickup_date=days_from_now(5), bid_start_at=mins(-25), bid_close_at=mins(8),
            forced_close_at=mins(20), trigger_window_minutes=10, extension_minutes=3,
            trigger_type="BID_RECEIVED")

        # 2. Active, extends on any rank change
        seed_auction(conn, mins(-40), [
            (mins(-28), make_quote("TCI Freight", 54000, 6000, 5000, 2)),
            (mins(-22), make_quote("Allcargo", 52000, 6500, 5000, 2)),
            (mins(-10), make_quote("Delhivery", 55000, 4000, 4000, 2)),
        ], name="Chennai Port → Bengaluru, 2x40ft containers", reference_id="RFQ-DEMO-02",
            pickup_date=days_from_now(7), bid_start_at=mins(-30), bid_close_at=mins(45),
            forced_close_at=mins(75), trigger_window_minutes=10, extension_minutes=5,
            trigger_type="ANY_RANK_CHANGE")

        # 3. Active, extends only when L1 changes
        seed_auction(conn, mins(-60), [
            (mins(-45), make_quote("Snowman Logistics", 120000, 8000, 7000, 5)),
            (mins(-30), make_quote("Coldex", 118000, 9000, 7000, 5)),
        ], name="Pune → Kolkata LTL pharma (reefer)", reference_id="RFQ-DEMO-03",
            pickup_date=days_from_now(10), bid_start_at=mins(-50), bid_close_at=mins(120),
            forced_close_at=mins(180), trigger_window_minutes=15, extension_minutes=5,
            trigger_type="L1_CHANGE")

        # 4. Past: extended twice, second extension capped -> FORCE_CLOSED
        seed_auction(conn, mins(-200), [
            (mins(-150), make_quote("Safexpress", 46000, 2000, 2000, 2)),
            (mins(-140), make_quote("Rivigo", 45000, 2000, 1500, 2)),
            (mins(-135), make_quote("Safexpress", 44000, 2000, 1500, 2)),   # outside window
            (mins(-125), make_quote("Rivigo", 43000, 2000, 1500, 2)),       # in window: -120 -> -115
            (mins(-118), make_quote("Safexpress", 42500, 2000, 1500, 2)),   # in window: -115 -> -112 (capped)
            (mins(-113), make_quote("Rivigo", 42000, 2000, 1500, 2)),       # trigger met, forced close reached
        ], name="Ahmedabad → Jaipur textile bales", reference_id="RFQ-DEMO-04",
            pickup_date=days_from_now(2), bid_start_at=mins(-190), bid_close_at=mins(-120),
            forced_close_at=mins(-112), trigger_window_minutes=10, extension_minutes=5,
            trigger_type="BID_RECEIVED")

        # 5. Past: closed normally
        seed_auction(conn, mins(-300), [
            (mins(-250), make_quote("Om Logistics", 38000, 1500, 1500, 2)),
            (mins(-200), make_quote("Spoton", 37000, 1500, 1500, 2)),
        ], name="Hyderabad → Nagpur auto parts", reference_id="RFQ-DEMO-05",
            pickup_date=days_from_now(1), bid_start_at=mins(-290), bid_close_at=mins(-60),
            forced_close_at=mins(-30), trigger_window_minutes=10, extension_minutes=5,
            trigger_type="L1_CHANGE")

        # 6. Upcoming
        seed_auction(conn, NOW, [],
            name="Delhi → Lucknow consumer electronics", reference_id="RFQ-DEMO-06",
            pickup_date=days_from_now(4), bid_start_at=mins(24 * 60), bid_close_at=mins(25 * 60),
            forced_close_at=mins(26 * 60), trigger_window_minutes=10, extension_minutes=5,
            trigger_type="ANY_RANK_CHANGE")

        sync_all_statuses(conn, NOW)
        counts = conn.execute("SELECT status, COUNT(*) AS n FROM rfqs GROUP BY status ORDER BY status").fetchall()
        print("Seeded:", ", ".join(f"{c['n']} {c['status']}" for c in counts))


if __name__ == "__main__":
    main()
