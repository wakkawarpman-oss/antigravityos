import re

with open('src/discovery_engine.py') as f:
    text = f.read()

# Remove data classes
text = re.sub(r'@dataclass\nclass Observable:.*?@property\n    def fingerprint\(self\) -> str:\n        return f"\{self\.obs_type\}:\{self\.value\}"\n\n', '', text, flags=re.DOTALL)
text = re.sub(r'@dataclass\nclass IdentityCluster:.*?sources: set\[str\] = field\(default_factory=set\)\n', '', text, flags=re.DOTALL)

# TIER constants
text = re.sub(r'TIER_CONFIRMED = "confirmed".*?TIER_UNVERIFIED = "unverified"\n', '', text, flags=re.DOTALL)

# Add imports
imports = """
from models.observables import Observable, IdentityCluster, TIER_CONFIRMED, TIER_PROBABLE, TIER_UNVERIFIED
from pipelines.resolution import EntityResolutionPipeline
"""
text = text.replace('from dataclasses import dataclass, field\n', 'from dataclasses import dataclass, field\n' + imports)

# Remove the methods that are now in EntityResolutionPipeline
methods_to_remove = ['resolve_entities', '_names_match', '_assign_tiers', '_link_observables', '_find_observable', '_build_clusters']

for meth in methods_to_remove:
    # Regex to remove def method(self, ...): ... up to next def or end of class
    # Better to use string manipulation
    pass

# Quick and dirty:
def remove_method(method_name, code):
    match = re.search(r'\n    def ' + method_name + r'\(.*?\):\n', code)
    if not match: return code
    start = match.start() + 1
    # find next method
    next_match = re.search(r'\n    def ', code[start+10:])
    if next_match:
        end = start + 10 + next_match.start()
        return code[:start] + code[end:]
    else:
        # end of class
        return code[:start]

for meth in methods_to_remove:
    text = remove_method(meth, text)

# Inject the facade for resolve_entities
facade = """
    def resolve_entities(self) -> list[IdentityCluster]:
        self.clusters = EntityResolutionPipeline(self.db, self._all_observables, self._platform_from_url).resolve_entities()
        return self.clusters
"""
text = text.replace('    def get_pivot_queue(', facade + '\n    def get_pivot_queue(')

with open('src/discovery_engine.py', 'w') as f:
    f.write(text)

