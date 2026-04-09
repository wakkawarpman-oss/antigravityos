from dataclasses import dataclass, field

TIER_CONFIRMED = "confirmed"
TIER_PROBABLE = "probable"
TIER_UNVERIFIED = "unverified"

@dataclass
class Observable:
    """A single discovered observable."""
    obs_type: str          # phone, email, username, domain, url
    value: str             # normalized value
    source_tool: str       # which tool found it
    source_target: str     # original target that was queried
    source_file: str       # metadata JSON path
    depth: int = 0         # discovery depth (0 = seed, 1 = first pivot, …)
    raw: str = ""          # original raw text
    urls: list[str] = field(default_factory=list)
    is_original_target: bool = False        # was this the investigation input?
    source_tools: set[str] = field(default_factory=set)  # all tools that found this
    tier: str = TIER_UNVERIFIED             # confirmed / probable / unverified

    @property
    def fingerprint(self) -> str:
        return f"{self.obs_type}:{self.value}"

@dataclass
class IdentityCluster:
    """A resolved identity — one real-world entity."""
    person_id: str
    label: str                                # display name
    observables: list[Observable] = field(default_factory=list)
    profile_urls: list[str] = field(default_factory=list)
    confidence: float = 0.0
    sources: set[str] = field(default_factory=set)
