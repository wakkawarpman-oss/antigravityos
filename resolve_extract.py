import re

with open('src/discovery_engine.py') as f:
    lines = f.readlines()

def get_block(func_name):
    start = -1
    for i, l in enumerate(lines):
        if l.strip().startswith(f"def {func_name}("):
            start = i
            break
    if start == -1: return ""
    indent = len(lines[start]) - len(lines[start].lstrip())
    block = [lines[start]]
    for l in lines[start+1:]:
        if len(l.strip()) > 0 and len(l) - len(l.lstrip()) <= indent:
            break
        block.append(l)
    return "".join(block)

with open('src/pipelines/resolution.py', 'w') as out:
    out.write("import math\nfrom models.observables import Observable, IdentityCluster, TIER_CONFIRMED, TIER_PROBABLE, TIER_UNVERIFIED\nimport uuid\nimport re\n\n")
    out.write(get_block('resolve_entities'))
    out.write('\n')
    out.write(get_block('_names_match'))
    out.write('\n')
    out.write(get_block('_assign_tiers'))
    out.write('\n')
    out.write(get_block('_link_observables'))
    out.write('\n')
    out.write(get_block('_find_observable'))
    out.write('\n')
    out.write(get_block('_build_clusters'))
    out.write('\n')
