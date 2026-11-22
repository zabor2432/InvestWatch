from investwatch_common.enums import Platform

from app.collectors.base import Collector
from app.collectors.reddit import RedditCollector
from app.collectors.stubs import FacebookCollector, InstagramCollector, XCollector
from app.collectors.substack import SubstackCollector
from app.collectors.telegram import TelegramCollector
from app.collectors.web import WebCollector
from app.collectors.wykop import WykopCollector
from app.collectors.youtube import YouTubeCollector

COLLECTORS: dict[Platform, type[Collector]] = {
    Platform.YOUTUBE: YouTubeCollector,
    Platform.TELEGRAM: TelegramCollector,
    Platform.WEB: WebCollector,
    Platform.REDDIT: RedditCollector,
    Platform.WYKOP: WykopCollector,
    Platform.SUBSTACK: SubstackCollector,
    Platform.FACEBOOK: FacebookCollector,
    Platform.INSTAGRAM: InstagramCollector,
    Platform.X: XCollector,
}
