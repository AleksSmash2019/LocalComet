"""Read-only browser safety policy with explicit approval barriers."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


DANGEROUS_ACTIONS = frozenset({"submit", "payment", "publish", "delete", "upload", "account_settings"})
USER_INTERVENTION_SIGNALS = frozenset({"login", "captcha", "2fa", "two_factor", "mfa"})


class BrowserStatus(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    WAITING_FOR_USER = "waiting_for_user"


@dataclass(frozen=True, slots=True)
class BrowserDecision:
    status: BrowserStatus
    action: str
    url: str
    reason_code: str
    requires_approval: bool = False
    takeover_reason: str | None = None


class BrowserSafetyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BrowserSafetyPolicy:
    """Policy-only browser gate; it never navigates or submits anything."""

    def __init__(self, allowlisted_domains: set[str] | frozenset[str]) -> None:
        normalized = {self._normalize_domain(domain) for domain in allowlisted_domains}
        if not normalized:
            raise BrowserSafetyError("ALLOWLIST_EMPTY", "at least one browser domain is required")
        self._allowlisted_domains = frozenset(normalized)

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        value = domain.strip().casefold().rstrip(".")
        if not value or "/" in value or ":" in value or " " in value:
            raise BrowserSafetyError("DOMAIN_INVALID", "allowlisted domain is invalid")
        return value

    def _check_url(self, url: str) -> str:
        if not isinstance(url, str) or len(url) > 2048:
            raise BrowserSafetyError("URL_INVALID", "browser URL is invalid")
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise BrowserSafetyError("URL_INVALID", "only http(s) URLs with a host are supported")
        if not any(hostname == domain or hostname.endswith("." + domain) for domain in self._allowlisted_domains):
            raise BrowserSafetyError("DOMAIN_NOT_ALLOWLISTED", "browser domain is not allowlisted")
        return hostname

    def decide(
        self,
        *,
        url: str,
        action: str = "read",
        approval_present: bool = False,
        user_intervention_signal: str | None = None,
    ) -> BrowserDecision:
        self._check_url(url)
        normalized_action = action.strip().casefold().replace(" ", "_")
        if not normalized_action:
            raise BrowserSafetyError("ACTION_INVALID", "browser action is required")
        if user_intervention_signal is not None:
            signal = user_intervention_signal.strip().casefold().replace("-", "_")
            if signal in USER_INTERVENTION_SIGNALS:
                return BrowserDecision(
                    BrowserStatus.WAITING_FOR_USER,
                    normalized_action,
                    url,
                    "USER_INTERVENTION_REQUIRED",
                    takeover_reason=signal,
                )
        if normalized_action in DANGEROUS_ACTIONS:
            if not approval_present:
                return BrowserDecision(
                    BrowserStatus.BLOCKED,
                    normalized_action,
                    url,
                    "APPROVAL_REQUIRED",
                    requires_approval=True,
                )
            return BrowserDecision(
                BrowserStatus.ALLOWED,
                normalized_action,
                url,
                "APPROVED_DANGEROUS_ACTION",
                requires_approval=True,
            )
        if normalized_action != "read":
            return BrowserDecision(BrowserStatus.BLOCKED, normalized_action, url, "READ_ONLY_ACTION_REQUIRED")
        return BrowserDecision(BrowserStatus.ALLOWED, "read", url, "READ_ONLY_ALLOWLISTED")


__all__ = [
    "BrowserDecision",
    "BrowserSafetyError",
    "BrowserSafetyPolicy",
    "BrowserStatus",
    "DANGEROUS_ACTIONS",
    "USER_INTERVENTION_SIGNALS",
]
