import math
import re
import uuid
import sqlite3

from models.observables import (
    Observable,
    IdentityCluster,
    TIER_CONFIRMED,
    TIER_PROBABLE,
    TIER_UNVERIFIED,
)

from discovery_repository import DiscoveryRepository

_HEX_ONLY_RE = re.compile(r"^[a-fA-F0-9]{16,}$")

class EntityResolutionPipeline:
    """Graph-based clustering for OSINT observables."""

    def __init__(self, repo: DiscoveryRepository, observables: list[Observable], platform_from_url_func):
        self.repo = repo
        self._all_observables = observables
        self._platform_from_url = platform_from_url_func

    def resolve_entities(self) -> list[IdentityCluster]:
        """Cluster all observables into identity anchors."""
        # Step 1: File-level co-occurrence (SAME log file = same tool session)
        session_groups: dict[str, list[Observable]] = {}
        for obs in self._all_observables:
            key = obs.source_file
            session_groups.setdefault(key, []).append(obs)

        for source_file, group in session_groups.items():
            unique = {obs.fingerprint: obs for obs in group}
            items = list(unique.values())
            if len(items) > 30:
                continue
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    if a.fingerprint == b.fingerprint:
                        continue
                    self._link_observables(a, b, "co_occurrence_file", 0.4)

        # Step 2: Pipeline-label co-occurrence is intentionally omitted as it was in engine

        # Step 3: Name-matching heuristic
        usernames = [o for o in self._all_observables if o.obs_type == "username"]
        for i, a in enumerate(usernames):
            for b in usernames[i + 1:]:
                if self._names_match(a.value, b.value):
                    self._link_observables(a, b, "name_match", 0.6)


        # Step 4: Assign verification tiers
        self._assign_tiers()

        # Step 5: Transitive closure → clusters
        return self._build_clusters()

    @staticmethod
    def _names_match(a: str, b: str) -> bool:
        """Check if two usernames are variants of the same name."""
        a_n = a.lower().replace(" ", "").replace("_", "").replace(".", "")
        b_n = b.lower().replace(" ", "").replace("_", "").replace(".", "")
        if not a_n or not b_n:
            return False
        if a_n == b_n:
            return True
        if len(a_n) > 3 and len(b_n) > 3 and (a_n in b_n or b_n in a_n):
            return True
        return False

    def _assign_tiers(self):
        """Assign verification tiers based on evidence quality."""
        for obs in self._all_observables:
            if obs.is_original_target:
                obs.tier = TIER_CONFIRMED
            elif obs.source_tool.startswith("confirmed_import") or any(tool.startswith("confirmed_import") for tool in obs.source_tools):
                obs.tier = TIER_CONFIRMED
            elif len(obs.source_tools) >= 2:
                obs.tier = TIER_CONFIRMED  # Multi-source corroboration
            elif obs.depth == 0:
                obs.tier = TIER_PROBABLE
            else:
                obs.tier = TIER_UNVERIFIED
            self.repo.update_observable_tier(obs.obs_type, obs.value, obs.tier)
        # self.repo.commit()  # commit is handled inside repo methods if needed, or explicitly at the end

    def _link_observables(self, a: Observable, b: Observable, reason: str, confidence: float):
        # Ensure consistent ordering
        key_a = (a.obs_type, a.value)
        key_b = (b.obs_type, b.value)
        if key_a > key_b:
            key_a, key_b = key_b, key_a
        self.repo.link_observables(key_a, key_b, reason, confidence)

    def _build_clusters(self) -> list[IdentityCluster]:
        """Union-Find transitive closure over entity_links — tier-aware."""
        nodes: dict[str, str] = {}
        all_obs_map: dict[str, Observable] = {}
        for obs in self._all_observables:
            fp = obs.fingerprint
            nodes[fp] = fp
            all_obs_map[fp] = obs

        def find(x: str) -> str:
            while nodes[x] != x:
                nodes[x] = nodes[nodes[x]]
                x = nodes[x]
            return x

        def union(a: str, b: str):
            ra, rb = find(a), find(b)
            if ra != rb:
                nodes[ra] = rb

        # Only apply links where at least one side is confirmed/probable
        for row in self.repo.get_entity_links():
            fp_a = f"{row[0]}:{row[1]}"
            fp_b = f"{row[2]}:{row[3]}"
            if fp_a in nodes and fp_b in nodes:
                obs_a = all_obs_map.get(fp_a)
                obs_b = all_obs_map.get(fp_b)
                if obs_a and obs_b:
                    a_trusted = obs_a.tier in (TIER_CONFIRMED, TIER_PROBABLE) or obs_a.is_original_target
                    b_trusted = obs_b.tier in (TIER_CONFIRMED, TIER_PROBABLE) or obs_b.is_original_target
                    if a_trusted or b_trusted:
                        union(fp_a, fp_b)

        groups: dict[str, list[Observable]] = {}
        for fp, obs in all_obs_map.items():
            root = find(fp)
            groups.setdefault(root, []).append(obs)

        clusters: list[IdentityCluster] = []
        for root, obs_list in groups.items():
            label = ""
            usernames = sorted(
                [o.value for o in obs_list if o.obs_type == "username" and o.tier != TIER_UNVERIFIED],
                key=lambda v: (-len(v.split()), -len(v)),
            )
            if not usernames:
                usernames = sorted(
                    [o.value for o in obs_list if o.obs_type == "username"],
                    key=lambda v: (-len(v.split()), -len(v)),
                )
            real_usernames = [
                u for u in usernames
                if len(u) > 3
                and not _HEX_ONLY_RE.fullmatch(u)
                and u.lower() not in ("accounts", "profile", "user.aspx", "search")
            ]
            if real_usernames:
                label = real_usernames[0]
            else:
                for pref in ("email", "phone", "domain"):
                    candidates = [o for o in obs_list if o.obs_type == pref]
                    if candidates:
                        label = candidates[0].value
                        break
            if not label:
                label = obs_list[0].value

            urls: list[str] = []
            seen_platforms: dict[str, str] = {}
            for obs in obs_list:
                if obs.obs_type == "username":
                    rows = self.repo.get_profile_urls_for_username(obs.value)
                    for r in rows:
                        url = r[0]
                        platform = self._platform_from_url(url)
                        if platform == "ucoz":
                            if "ucoz" not in seen_platforms:
                                seen_platforms["ucoz"] = url
                                urls.append(url)
                        else:
                            urls.append(url)

            confirmed_count = sum(1 for o in obs_list if o.tier == TIER_CONFIRMED)
            probable_count = sum(1 for o in obs_list if o.tier == TIER_PROBABLE)
            total = len(obs_list)
            if total == 0:
                confidence = 0.0
            else:
                quality_ratio = (confirmed_count * 1.0 + probable_count * 0.5) / total
                source_tools_set = {obs.source_tool for obs in obs_list}
                tool_bonus = min(0.2, 0.05 * len(source_tools_set))
                cluster_fingerprints = {obs.fingerprint for obs in obs_list}
                max_link_confidence = 0.0
                for row in self.repo.get_entity_links():
                    fp_a = f"{row[0]}:{row[1]}"
                    fp_b = f"{row[2]}:{row[3]}"
                    if fp_a in cluster_fingerprints and fp_b in cluster_fingerprints:
                        max_link_confidence = max(max_link_confidence, float(row[4] or 0.0))
                link_bonus = 0.05 if max_link_confidence >= 0.9 else 0.0
                confidence = min(0.95, quality_ratio * 0.7 + tool_bonus + link_bonus + 0.1)

            source_tools_set = {obs.source_tool for obs in obs_list}
            cluster = IdentityCluster(
                person_id=str(uuid.uuid4()),
                label=label,
                observables=obs_list,
                profile_urls=sorted(set(urls)),
                confidence=confidence,
                sources=source_tools_set,
            )
            clusters.append(cluster)

        clusters.sort(key=lambda c: (sum(1 for o in c.observables if o.tier == TIER_CONFIRMED), len(c.observables)), reverse=True)
        return clusters
