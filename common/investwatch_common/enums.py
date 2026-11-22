from enum import StrEnum


class Platform(StrEnum):
    YOUTUBE = "youtube"
    TELEGRAM = "telegram"
    WEB = "web"
    REDDIT = "reddit"
    WYKOP = "wykop"
    SUBSTACK = "substack"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    X = "x"


class Task(StrEnum):
    REGISTRY_ADS = "registry_ads"  # module 1: ads of firms listed by KNF
    FIRM_MARKETING = "firm_marketing"  # module 2: marketing published by the KNF-listed firms themselves
    SHADOW_ADVISORY = "shadow_advisory"  # module 3: unauthorised advisory offers
    REGISTRY_SYNC = "registry_sync"  # refresh of the KNF / I-SCAN registers


class MediaType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class MediaKind(StrEnum):
    IMAGE = "image"
    THUMBNAIL = "thumbnail"
    SCREENSHOT = "screenshot"  # rendered page (module 2: font size, contrast, position of risk warnings)


class TranscriptStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


class JobTrigger(StrEnum):
    MANUAL = "manual"
    CRON = "cron"


class FirmKind(StrEnum):
    AUTHORIZED = "authorized"  # listed in a KNF register of investment firms / credit institutions
    REVOKED = "revoked"  # KNF revoked the brokerage licence
    WARNED = "warned"  # KNF public warning list or I-SCAN warning
    AGENT = "agent"  # registered agent acting on behalf of an investment firm (not a firm itself)


class RegistryList(StrEnum):
    BROKERAGE_BANKS = "brokerage_banks"
    BROKERAGE_FIRMS = "brokerage_firms"
    FOREIGN_BRANCHES = "foreign_investment_firms"
    FOREIGN_NO_BRANCH = "foreign_investment_firms_without_branches"
    CREDIT_INSTITUTIONS_BRANCHES = "credit_institutions_branches"
    CREDIT_INSTITUTIONS_CROSS_BORDER = "credit_institutions_cross_border"
    REVOKED_LICENCES = "revoked_licences"
    KNF_PUBLIC_WARNINGS = "knf_public_warnings"
    ISCAN_WARNINGS = "iscan_warnings"
    AGENTS_LEGAL = "investment_firm_agents_legal"  # agents: legal persons / organisational units
    AGENTS_NATURAL = "investment_firm_agents_natural"  # agents: natural persons (public register, personal data)


FIRM_KIND_BY_LIST: dict[RegistryList, FirmKind] = {
    RegistryList.BROKERAGE_BANKS: FirmKind.AUTHORIZED,
    RegistryList.BROKERAGE_FIRMS: FirmKind.AUTHORIZED,
    RegistryList.FOREIGN_BRANCHES: FirmKind.AUTHORIZED,
    RegistryList.FOREIGN_NO_BRANCH: FirmKind.AUTHORIZED,
    RegistryList.CREDIT_INSTITUTIONS_BRANCHES: FirmKind.AUTHORIZED,
    RegistryList.CREDIT_INSTITUTIONS_CROSS_BORDER: FirmKind.AUTHORIZED,
    RegistryList.REVOKED_LICENCES: FirmKind.REVOKED,
    RegistryList.KNF_PUBLIC_WARNINGS: FirmKind.WARNED,
    RegistryList.ISCAN_WARNINGS: FirmKind.WARNED,
    RegistryList.AGENTS_LEGAL: FirmKind.AGENT,
    RegistryList.AGENTS_NATURAL: FirmKind.AGENT,
}
