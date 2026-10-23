#..

from datetime import datetime, timedelta, timezone #time stuff


def iso(minutes): 
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat() #future or past!


def rfq_payload(**overrides): 
    body = {
        "name": "API RFQ",
        "pickupDate": "2030-01-10",
        "bidStartAt": iso(-1), 
        "bidCloseAt": iso(5), #c
        "forcedCloseAt": iso(8), #
        "triggerWindowMinutes": 10,
        "extensionMinutes": 5,
        "triggerType": "BID_RECEIVED",
    }
    body.update(overrides) #overrides
    return body


def bid_payload(**overrides): #default bid
    body = {
        "carrierName": "Gati",
        "freightCharges": 1000,
        "originCharges": 100,
        "destinationCharges": 50.5,
        "transitTimeDays": 3,
        "quoteValidUntil": "2030-01-31",
    }
    body.update(overrides) #.
    return body


def test_health(client): #check?
    assert client.get("/api/health").json() == {"ok": True}


def test_create_validation_error_format(client): 
    res = client.post("/api/rfqs", json=rfq_payload(name="", triggerType="NOPE", extensionMinutes=0))
    assert res.status_code == 400 #rejected?
    body = res.json()
    assert body["error"] == "Validation failed"
    assert set(body["details"]) == {"name", "triggerType", "extensionMinutes"} #all flagged!


def test_create_forced_before_close(client): #
    res = client.post("/api/rfqs", json=rfq_payload(forcedCloseAt=iso(4)))
    assert res.status_code == 400 and "forcedCloseAt" in res.json()["details"] 

def test_full_flow(client): 
    created = client.post("/api/rfqs", json=rfq_payload()).json()["rfq"]
    assert created["status"] == "ACTIVE" and created["referenceId"].startswith("RFQ-") #
    assert created["config"] == {"triggerWindowMinutes": 10, "extensionMinutes": 5, "triggerType": "BID_RECEIVED"} #config saved

    res = client.post(f"/api/rfqs/{created['id']}/bids", json=bid_payload())
    assert res.status_code == 201 #bid accepted!
    result = res.json()
    assert result["rank"] == 1 and result["extension"]["reason"].startswith("Bid received from Gati") #triggered the extension

    lower = client.post(f"/api/rfqs/{created['id']}/bids", json=bid_payload(freightCharges=2000))
    assert lower.status_code == 422 #higher bid rejected?

    listing = client.get("/api/rfqs").json()
    row = listing["rfqs"][0]
    assert "serverTime" in listing #clock synced
    assert row["lowestBid"] == {"amount": 1150.5, "carrierName": "Gati"} 
    assert row["extensionCount"] == 1 #one extension

    d = client.get(f"/api/rfqs/{created['id']}").json()
    assert d["rankings"][0]["label"] == "L1" # top dog
    assert d["bids"][0]["isCurrent"] is True # latest bid
    assert [a["eventType"] for a in d["activity"]] == ["RFQ_CREATED", "BID_SUBMITTED", "TIME_EXTENDED"] #correct order


def test_not_found_and_bad_json(client): #edge cases
    assert client.get("/api/rfqs/999").status_code == 404 #missing id
    assert client.get("/api/rfqs/abc").status_code == 404 
    res = client.post("/api/rfqs", content="{bad", headers={"content-type": "application/json"})
    assert res.status_code == 400 and res.json()["error"] == "Invalid JSON body" #garbage in!!!!
