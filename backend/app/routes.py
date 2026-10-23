##

from collections.abc import Iterator
from datetime import datetime
import psycopg
from fastapi import APIRouter, Depends, Request #fastapi kit!!
from .auction import create_rfq, get_rfq_detail, list_rfqs, make_rfq_dict, submit_bid, utcnow #core
from .schemas import BidCreate, BidResult, RfqCreate, RfqCreateResponse, RfqDetailResponse, RfqListResponse #schemas


def get_conn(request: Request) -> Iterator[psycopg.Connection]: # db dependency
    with request.app.state.pool.connection() as conn:
        yield conn #f

def get_now() -> datetime: #time dependency!!
    return utcnow() #server time


router = APIRouter(prefix="/rfqs", tags=["RFQs / British Auctions"]) # mount here


@router.get("", response_model=RfqListResponse) #list all
def list_auctions(conn=Depends(get_conn), now: datetime = Depends(get_now)):
    return {"server_time": now, "rfqs": list_rfqs(conn, now)} #with the clock

@router.post("", response_model=RfqCreateResponse, status_code=201) #create one
def create_auction(body: RfqCreate, conn=Depends(get_conn), now: datetime = Depends(get_now)):
    return {"rfq": make_rfq_dict(create_rfq(conn, body, now), now)} 

@router.get("/{rfq_id}", response_model=RfqDetailResponse)
def auction_detail(rfq_id: int, conn=Depends(get_conn), now: datetime = Depends(get_now)):
    return {"server_time": now, **get_rfq_detail(conn, rfq_id, now)} #spread the detail

@router.post("/{rfq_id}/bids", response_model=BidResult, status_code=201) #place the bid
def place_bid(rfq_id: int, body: BidCreate, conn=Depends(get_conn), now: datetime = Depends(get_now)):
    return submit_bid(conn, rfq_id, body, now) #
