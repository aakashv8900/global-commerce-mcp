"""Alerts module for real-time notifications."""

from .engine import AlertEngine
from .triggers import (
    AlertTrigger,
    PriceDropTrigger,
    StockoutTrigger,
    TrendChangeTrigger,
    ArbitrageTrigger,
    RankChangeTrigger,
)
from .channels import NotificationChannelBase, WebhookChannel, MCPChannel

__all__ = [
    "AlertEngine",
    "AlertTrigger",
    "PriceDropTrigger",
    "StockoutTrigger",
    "TrendChangeTrigger",
    "ArbitrageTrigger",
    "RankChangeTrigger",
    "NotificationChannelBase",
    "WebhookChannel",
    "MCPChannel",
]
