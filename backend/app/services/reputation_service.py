"""
Reputation / threat-intelligence integration layer.

DESIGN STATUS (honest): no reputation provider is integrated in this
prototype. This module exists to define the seam where Google Safe
Browsing, PhishTank, or similar providers could be added later, and to
report an explicit "not integrated" status.

Status semantics (must be preserved by future providers):
  confirmed_match   - the provider returned a verified malicious listing
  no_match          - the provider returned no listing. THIS IS NOT PROOF
                      OF SAFETY. Coverage is incomplete by definition.
  unknown           - provider reachable but result indeterminate
  unavailable       - provider not configured, unreachable, rate-limited
"""

from __future__ import annotations

from app.core.config import Settings


class ReputationProvider:
    name = "abstract"

    def check(self, url: str) -> dict:  # noqa: ARG002 - interface
        raise NotImplementedError


class NoProviderConfigured(ReputationProvider):
    name = "none"

    def check(self, url: str) -> dict:  # noqa: ARG002
        return {
            "provider": "none",
            "status": "unavailable",
            "message": (
                "No threat-intelligence provider is configured or integrated "
                "in this prototype. The prediction comes solely from the "
                "locally trained model and URL analysis."
            ),
        }


def build_reputation_service(settings: Settings) -> ReputationProvider:
    configured = [p.strip() for p in settings.reputation_providers.split(",") if p.strip()]
    if not configured:
        return NoProviderConfigured()
    # Future: map provider names to implementations here. Unknown names are
    # never silently treated as checked; they surface as unavailable.
    return NoProviderConfigured()
