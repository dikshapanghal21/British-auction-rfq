##..

from concurrent.futures import ThreadPoolExecutor #parallel workers
from datetime import date, datetime, timedelta, timezone #time 

import pytest

from app.auction import create_rfq, get_rfq_detail, submit_bid, sync_all_statuses # core
from app.db import connect 
from app.errors import ApiError #custom error
from app.schemas import BidCreate, RfqCreate #input schemas

from .conftest import TEST_DATABASE_URL

T0 = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc) #fixed anchor!


def at(minutes): #offset helper
    return T0 + timedelta(minutes=minutes)


#default auction: start 12:00, close 18:00 (360 min), forced 18:20 (380). X=10, Y=5!!
def make_rfq(conn, **overrides): #create rfq
    cfg = dict(
        name="Test RFQ",
        pickup_date=date(2030, 1, 10),
        bid_start_at=at(0),
        bid_close_at=at(360),
        forced_close_at=at(380),
        trigger_window_minutes=10,
        extension_minutes=5,
        trigger_type="BID_RECEIVED",
    )
    cfg.update(overrides) 
    return create_rfq(conn, RfqCreate(**cfg), T0)


def bid(conn, rfq, carrier, total, minute): #place the bid
    return submit_bid(conn, rfq["id"], BidCreate(
        carrier_name=carrier,
        freight_charges=total,
        origin_charges=0,
        destination_charges=0,
        transit_time_days=2,
        quote_valid_until=date(2030, 2, 1),
    ), at(minute))

 
def detail(conn, rfq, minute=0): # get the detail
    return get_rfq_detail(conn, rfq["id"], at(minute))

def raises(status, fn, field=None): # expect the error
    with pytest.raises(ApiError) as e:
        fn()
    assert e.value.status == status 
    if field:
        assert field in e.value.details 
    return e.value

# RFQ validation >>
def test_forced_close_must_be_after_bid_close(conn): #date order
    raises(400, lambda: make_rfq(conn, forced_close_at=at(360)), "forcedCloseAt")
    raises(400, lambda: make_rfq(conn, forced_close_at=at(300)), "forcedCloseAt")


def test_bid_close_must_be_after_start(conn): # 
    raises(400, lambda: make_rfq(conn, bid_close_at=at(0)), "bidCloseAt")


def test_reference_id_auto_generated_and_unique(conn): #no duplicates
    assert make_rfq(conn)["reference_id"] == "RFQ-00001" #first ever
    make_rfq(conn, reference_id="ABC-1")
    raises(409, lambda: make_rfq(conn, reference_id="ABC-1"), "referenceId") #collision caught!!

def test_db_constraint_blocks_close_beyond_forced(conn): #db enforced
    rfq = make_rfq(conn)
    with pytest.raises(Exception):
        conn.execute(
            "UPDATE rfqs SET current_close_at = forced_close_at + interval '1 second' WHERE id = %s",
            (rfq["id"],),
        )

# bid rules
def test_rejects_bids_before_start_and_after_close(conn): #timing check
    rfq = make_rfq(conn, bid_start_at=at(10))
    raises(409, lambda: bid(conn, rfq, "A", 1000, 5)) #early
    raises(409, lambda: bid(conn, rfq, "A", 1000, 360)) #late


def test_supplier_must_lower_own_quote(conn): #
    rfq = make_rfq(conn)
    bid(conn, rfq, "A", 1000, 10)
    raises(422, lambda: bid(conn, rfq, "A", 1000, 20)) # same price
    raises(422, lambda: bid(conn, rfq, "a", 1200, 20)) 
    bid(conn, rfq, "A", 900, 20) #lower wins


def test_ranking_lowest_first_tie_goes_to_earlier_bid(conn): #tie broken
    rfq = make_rfq(conn)
    bid(conn, rfq, "A", 1000, 10)
    bid(conn, rfq, "B", 900, 20)
    bid(conn, rfq, "C", 900, 30)
    ranks = [(r["label"], r["carrier_name"]) for r in detail(conn, rfq, 40)["rankings"]]
    assert ranks == [("L1", "B"), ("L2", "C"), ("L3", "A")] #earlier wins tie


def test_total_is_sum_of_charges(conn): 
    rfq = make_rfq(conn)
    submit_bid(conn, rfq["id"], BidCreate(
        carrier_name="A",
        freight_charges="1000.50",
        origin_charges="200.25",
        destination_charges="99.25",
        transit_time_days=2,
        quote_valid_until=date(2030, 2, 1),
    ), at(10))
    assert detail(conn, rfq, 11)["rankings"][0]["total_amount"] == 1300.0 #adds up


# trigger: BID RECEIVED >>
def test_bid_outside_window_does_not_extend(conn): 
    rfq = make_rfq(conn)
    assert bid(conn, rfq, "A", 1000, 349)["extension"] is None  #window starts at 350
    assert detail(conn, rfq)["rfq"]["current_close_at"] == at(360) 

def test_bid_inside_window_extends_by_y(conn): 
    rfq = make_rfq(conn)
    res = bid(conn, rfq, "A", 1000, 355)
    assert res["extension"]["new_close_at"] == at(365) # +5 min
    assert detail(conn, rfq)["rfq"]["current_close_at"] == at(365) # saved too

def test_window_moves_with_new_close(conn): #window shifts
    rfq = make_rfq(conn)
    bid(conn, rfq, "A", 1000, 355)  #close > 18:05, window now 17:55-18:05
    assert bid(conn, rfq, "B", 900, 356)["extension"]["new_close_at"] == at(370) #chains

def test_extension_never_exceeds_forced_close_then_force_closed(conn): #hard cap
    rfq = make_rfq(conn)
    bid(conn, rfq, "A", 1000, 355)  #18:05
    bid(conn, rfq, "B", 900, 360)   #18:10
    bid(conn, rfq, "A", 800, 365)   #18:15
    assert bid(conn, rfq, "B", 700, 370)["extension"]["new_close_at"] == at(380)  #= forced
    res = bid(conn, rfq, "A", 600, 375)  #trigger met, already at forced close
    assert res["extension"] is None and "forced close" in res["note"] 
    raises(409, lambda: bid(conn, rfq, "B", 500, 380)) #door closed

    sync_all_statuses(conn, at(381))
    d = detail(conn, rfq, 381)
    assert d["rfq"]["status"] == "FORCE_CLOSED" #
    assert d["rfq"]["extension_count"] == 4 
    assert any(a["event_type"] == "AUCTION_FORCE_CLOSED" for a in d["activity"]) 


def test_partial_extension_is_capped(conn): # partial ext
    rfq = make_rfq(conn, forced_close_at=at(362))
    ext = bid(conn, rfq, "A", 1000, 355)["extension"]
    assert ext["new_close_at"] == at(362) and ext["capped"] is True # capped flag


def test_normal_close_is_closed_not_force_closed(conn): # normal end
    rfq = make_rfq(conn)
    bid(conn, rfq, "A", 1000, 100)
    sync_all_statuses(conn, at(361))
    d = detail(conn, rfq, 361)
    assert d["rfq"]["status"] == "CLOSED" # not forced
    assert [a["event_type"] for a in d["activity"]].count("AUCTION_CLOSED") == 1 # once only


# -trigger: ANY_RANK_CHANGE
def test_rank_change_trigger(conn):
    rfq = make_rfq(conn, trigger_type="ANY_RANK_CHANGE")
    bid(conn, rfq, "A", 1000, 100)
    bid(conn, rfq, "B", 1100, 110)
    assert bid(conn, rfq, "B", 1050, 352)["extension"] is None  
    ext = bid(conn, rfq, "B", 900, 358)["extension"]           
    assert ext["new_close_at"] == at(365) # 
    assert "B L2→L1, A L1→L2" in ext["reason"] 


def test_new_supplier_entering_counts_as_rank_change(conn): # new entry
    rfq = make_rfq(conn, trigger_type="ANY_RANK_CHANGE")
    bid(conn, rfq, "A", 1000, 100)
    assert bid(conn, rfq, "C", 2000, 355)["extension"]["new_close_at"] == at(365) # counts


# trigger: L1_CHANGE
def test_l1_change_trigger(conn): # op dog change
    rfq = make_rfq(conn, trigger_type="L1_CHANGE")
    bid(conn, rfq, "A", 1000, 100)
    bid(conn, rfq, "B", 1200, 110)
    bid(conn, rfq, "C", 1300, 120)
    assert bid(conn, rfq, "C", 1100, 351)["extension"] is None  #L3 > L2, not L1
    assert bid(conn, rfq, "A", 950, 352)["extension"] is None   #L1 lowers but stays L1
    ext = bid(conn, rfq, "C", 900, 359)["extension"]        #C becomes L1
    assert ext["new_close_at"] == at(365) 
    assert "A → C" in ext["reason"] 


# activity log
def test_activity_log_records_bids_and_extensions_with_reason(conn): 
    rfq = make_rfq(conn)
    bid(conn, rfq, "A", 1000, 100)
    bid(conn, rfq, "B", 900, 355)
    activity = detail(conn, rfq, 356)["activity"]
    assert [a["event_type"] for a in activity] == ["RFQ_CREATED", "BID_SUBMITTED", "BID_SUBMITTED", "TIME_EXTENDED"] # correct order
    ext = activity[-1]
    assert (ext["old_close_at"], ext["new_close_at"]) == (at(360), at(365)) #t
    assert "Bid received from B" in ext["reason"] #


# concurrency
def test_concurrent_bids_are_serialised_by_row_lock(conn):
    """30 suppliers bid at the same instant: extensions must chain and stop at forced close."""
    rfq = make_rfq(conn, forced_close_at=at(400), extension_minutes=2, trigger_window_minutes=60)

    def place(i): 
        with connect(TEST_DATABASE_URL) as c:
            return bid(c, rfq, f"Carrier {i}", 10_000 - i, 359)

    with ThreadPoolExecutor(max_workers=10) as pool: #fire all
        results = list(pool.map(place, range(30)))

    exts = sorted((r["extension"] for r in results if r["extension"]), key=lambda e: e["old_close_at"])
    assert exts[0]["old_close_at"] == at(360) # 
    for prev, nxt in zip(exts, exts[1:]):
        assert nxt["old_close_at"] == prev["new_close_at"]  #no lost updates
    assert exts[-1]["new_close_at"] == at(400) #hits cap
    assert len(exts) == 20  #360 > 400 in steps of 2
    d = detail(conn, rfq, 359)
    assert d["rfq"]["current_close_at"] == at(400) and d["rfq"]["extension_count"] == 20 
