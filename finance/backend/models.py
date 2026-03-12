from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sms_raw = Column(Text, nullable=False)
    transaction_type = Column(String, nullable=False)
    account = Column(String, nullable=True)
    amount = Column(Float, default=0.0)
    currency = Column(String, default="AED")
    value_aed = Column(Float, default=0.0)
    date = Column(String, nullable=True)
    time = Column(String, nullable=True)
    merchant = Column(String, nullable=True)
    category = Column(String, default="Other")
    flow_type = Column(String, default="Outflow")
    deleted = Column(Boolean, default=False)


class TransactionOut(BaseModel):
    id: int
    created_at: datetime
    sms_raw: str
    transaction_type: str
    account: Optional[str]
    amount: float
    currency: str
    value_aed: float
    date: Optional[str]
    time: Optional[str]
    merchant: Optional[str]
    category: str
    flow_type: str

    model_config = {"from_attributes": True}


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    merchant: Optional[str] = None


class SummaryOut(BaseModel):
    total_inflow: float
    total_outflow: float
    by_category_spend: list[dict]
    by_category_income: list[dict]
    by_account: list[dict]
    by_month: list[dict]
    by_day: list[dict]
