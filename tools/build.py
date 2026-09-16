#!/usr/bin/env python3
"""Regenerate every file in this repo that is derived from another one.

Sources, which you edit by hand:

    networks.json                    which forknets exist and where each is in its life
    networks/<net>/pools.json        one object per pool on that forknet
    mempool/upstream-pools-v2.json   mempool's own list, verbatim, re-synced wholesale

Generated, which you do not:

    networks/<net>/pools-v2.json     upstream + that net's pools, in mempool's format
    pools.json                       a copy of the root network's pools.json
    pools-v2.json                    a copy of the root network's pools-v2.json

The two files at the root exist so the URLs the block explorer and the mempool
instance already fetch keep working while the forknets come and go underneath
them. `root_network` in networks.json decides which forknet they mirror; move it
when the network of record moves, and those consumers follow without being
reconfigured.

    python3 tools/build.py           write the generated files
    python3 tools/build.py --check   exit 1 if any of them is stale, touching nothing

No dependencies, no network access: everything it needs is already in the repo.
"""

import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    "name", "operator", "chain", "mode", "fee_bps",
    "coinbase_tag", "stratum_url", "operator_address",
]

# Fields a pool object is allowed to carry. Anything else is a typo until it is
# added here and to the table in README.md.
KNOWN = set(REQUIRED) | {
    "dashboard_url", "status_url", "pool_btc_address", "coinbase_addresses",
    "payout", "software", "logo", "contact", "mempool_id",
}


def load(path):
    with open(path) as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def coinbase_addresses(pool, problems, where):
    """The addresses that actually land in this pool's coinbase.

    Pooled payouts pay the pool address. A solo pool still takes its fee cut in
    the coinbase, so it pays the operator address. A zero-fee pool pays neither
    and nothing but the tag can identify it -- unless it is an operator mining
    for itself, which does pay, and says so with an explicit
    `coinbase_addresses`.
    """
    if "coinbase_addresses" in pool:
        return list(pool["coinbase_addresses"])
    if pool.get("pool_btc_address"):
        return [pool["pool_btc_address"]]
    if pool.get("fee_bps", 0) > 0 and pool.get("operator_address"):
        return [pool["operator_address"]]
    problems.append(
        f"{where}: fee_bps is 0 and no pool_btc_address, so nothing but the coinbase "
        f"tag can identify this pool. If an address does land in its coinbase -- a solo "
        f"operator mining for itself, say -- set \"coinbase_addresses\" explicitly."
    )
    return []


def mempool_entries(net, pools, problems):
    base = net["mempool_id_base"]
    entries, seen_ids = [], {}
    for i, pool in enumerate(pools):
        where = f"{net['id']}/{pool.get('name', f'pool #{i}')}"
        pid = pool.get("mempool_id", base + i)
        if pid in seen_ids:
            problems.append(f"{where}: mempool id {pid} is already taken by {seen_ids[pid]}.")
        seen_ids[pid] = where
        entries.append(OrderedDict([
            ("id", pid),
            ("name", pool["name"]),
            ("addresses", coinbase_addresses(pool, problems, where)),
            ("tags", [pool["coinbase_tag"]]),
            ("link", pool.get("dashboard_url") or ""),
        ]))
    return entries


def check_pool(pool, net_id, i, problems):
    where = f"{net_id}/{pool.get('name', f'pool #{i}')}"
    for field in REQUIRED:
        if field not in pool:
            problems.append(f"{where}: required field \"{field}\" is missing.")
    for field in pool:
        if field not in KNOWN:
            problems.append(f"{where}: unknown field \"{field}\" -- typo, or add it to README.md.")
    if pool.get("chain") != net_id:
        problems.append(
            f"{where}: \"chain\" reads {pool.get('chain')!r} but the file lives under "
            f"networks/{net_id}/. One of the two is wrong."
        )
    logo = pool.get("logo")
    if logo and not (ROOT / logo).exists():
        problems.append(f"{where}: logo {logo} is not committed -- the card will fall back to a monogram.")
    return where


def build():
    manifest = load(ROOT / "networks.json")
    upstream = load(ROOT / "mempool" / "upstream-pools-v2.json")
    nets = {n["id"]: n for n in manifest["networks"]}

    for key in ("root_network", "default_network"):
        if manifest[key] not in nets:
            raise SystemExit(f"networks.json: {key} is {manifest[key]!r}, which is not a listed network.")

    generated, problems = {}, []

    for net in manifest["networks"]:
        src = ROOT / "networks" / net["id"] / "pools.json"
        if not src.exists():
            problems.append(
                f"{net['id']}: listed in networks.json but {src.relative_to(ROOT)} does not exist. "
                f"Retiring it? Drop its entry from networks.json too."
            )
            continue

        data = load(src)
        if data.get("network") != net["id"]:
            problems.append(f"{net['id']}: pools.json says \"network\": {data.get('network')!r}.")

        tags = {}
        for i, pool in enumerate(data["pools"]):
            where = check_pool(pool, net["id"], i, problems)
            tag = pool.get("coinbase_tag")
            if tag in tags:
                problems.append(
                    f"{where}: coinbase_tag {tag!r} is already claimed by {tags[tag]} on this "
                    f"forknet. Both pools' blocks would be attributed to one of them."
                )
            tags[tag] = where

        entries = upstream + mempool_entries(net, data["pools"], problems)
        generated[f"networks/{net['id']}/pools-v2.json"] = dump(entries)

    if problems:
        raise SystemExit("\n".join("  - " + p for p in problems))

    root = manifest["root_network"]
    root_pools = load(ROOT / "networks" / root / "pools.json")
    header = OrderedDict()
    header["$comment"] = (
        f"GENERATED -- do not edit. A copy of networks/{root}/pools.json, published here so the "
        f"block explorer and anything else already fetching /pools.json keeps working as the "
        f"forknets change underneath it. Which network this mirrors is set by \"root_network\" in "
        f"networks.json. Edit networks/{root}/pools.json and run tools/build.py."
    )
    for k, v in root_pools.items():
        if k != "$comment":
            header[k] = v
    generated["pools.json"] = dump(header)
    generated["pools-v2.json"] = generated[f"networks/{root}/pools-v2.json"]

    return generated


def main(argv):
    check = "--check" in argv[1:]
    generated = build()

    stale = []
    for rel, text in sorted(generated.items()):
        path = ROOT / rel
        current = path.read_text() if path.exists() else None
        if current == text:
            continue
        stale.append(rel)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    if check:
        if stale:
            print("stale, run tools/build.py:")
            print("\n".join("  - " + s for s in stale))
            return 1
        print(f"up to date ({len(generated)} generated files)")
        return 0

    print("wrote" if stale else "up to date", end=" ")
    print(", ".join(stale) if stale else f"({len(generated)} generated files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
