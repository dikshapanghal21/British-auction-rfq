from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True)


class TriggerType(str, Enum):
    BID_RECEIVED = "BID_RECEIVED"
    ANY_RANK_CHANGE = "ANY_RANK_CHANGE"
    L1_CHANGE = "L1_CHANGE"


class AuctionStatus(str, Enum):
    UPCOMING = "UPCOMING"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    FORCE_CLOSED = "FORCE_CLOSED"


Money = Annotated[Decimal, Field(ge=0, le=Decimal("999999999.99"), decimal_places=2)]


class RfqCreate(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    reference_id: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{2,40}$")] | None = None
    pickup_date: date
    bid_start_at: AwareDatetime
    bid_close_at: AwareDatetime
    forced_close_at: AwareDatetime
    trigger_window_minutes: int = Field(ge=1, le=1440)
    extension_minutes: int = Field(ge=1, le=1440)
    trigger_type: TriggerType

    @field_validator("reference_id", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


class BidCreate(ApiModel):
    carrier_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    freight_charges: Money
    origin_charges: Money
    destination_charges: Money
    transit_time_days: int = Field(ge=1, le=365)
    quote_valid_until: date

    @property
    def total(self):
        return self.freight_charges + self.origin_charges + self.destination_charges


class AuctionConfig(ApiModel):
    trigger_window_minutes: int
    extension_minutes: int
    trigger_type: TriggerType


class RfqOut(ApiModel):
    id: int
    reference_id: str
    name: str
    pickup_date: date
    bid_start_at: datetime
    bid_close_at: datetime
    current_close_at: datetime
    forced_close_at: datetime
    status: AuctionStatus
    extension_count: int
    config: AuctionConfig
    created_at: datetime


class LowestBid(ApiModel):
    amount: float
    carrier_name: str


class RfqListItem(RfqOut):
    bid_count: int
    supplier_count: int
    lowest_bid: LowestBid | None


class RfqListResponse(ApiModel):
    server_time: datetime
    rfqs: list[RfqListItem]


class RfqCreateResponse(ApiModel):
    rfq: RfqOut


class BidOut(ApiModel):
    id: int
    supplier_id: int
    carrier_name: str
    freight_charges: float
    origin_charges: float
    destination_charges: float
    total_amount: float
    transit_time_days: int
    quote_valid_until: date
    created_at: datetime


class RankedBid(BidOut):
    rank: int
    label: str


class BidHistoryItem(BidOut):
    is_current: bool


class ActivityOut(ApiModel):
    id: int
    event_type: str
    message: str
    reason: str | None
    bid_id: int | None
    carrier_name: str | None
    old_close_at: datetime | None
    new_close_at: datetime | None
    created_at: datetime


class RfqDetailResponse(ApiModel):
    server_time: datetime
    rfq: RfqOut
    rankings: list[RankedBid]
    bids: list[BidHistoryItem]
    activity: list[ActivityOut]


class ExtensionOut(ApiModel):
    old_close_at: datetime
    new_close_at: datetime
    reason: str
    capped: bool


class BidResult(ApiModel):
    bid_id: int
    rank: int
    extension: ExtensionOut | None
    note: str | None
