"""Platforms out of POC scope: login walls and anti-bot protection. Same interface, ready to implement."""

from collections.abc import Iterator

from investwatch_common.enums import Platform

from app.collectors.base import Collector, CollectorUnavailable
from app.models import RawPost


class _NotImplementedCollector(Collector):
    reason = "not implemented in the POC"

    def check_available(self) -> None:
        raise CollectorUnavailable(f"{self.platform}: {self.reason}")

    def search(self, query: str, limit: int) -> Iterator[RawPost]:
        raise CollectorUnavailable(f"{self.platform}: {self.reason}")


class FacebookCollector(_NotImplementedCollector):
    platform = Platform.FACEBOOK
    reason = "requires login; Meta Ad Library API requires identity verification"


class InstagramCollector(_NotImplementedCollector):
    platform = Platform.INSTAGRAM
    reason = "requires login"


class XCollector(_NotImplementedCollector):
    platform = Platform.X
    reason = "requires login or the paid API"
