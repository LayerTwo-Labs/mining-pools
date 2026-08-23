# eCash forknet mining pools

The list behind **pools.ecash.com**, and the source of pool attribution for the
block explorer.

* `pools.json` — the data. One object per pool. **This is the file you edit.**
* `index.html` — a static page that renders `pools.json` in the browser. No build
  step, no dependencies, no network calls beyond fetching `pools.json` from the
  same origin.
* `pools-v2.json` — the same pools in mempool's pool-attribution format, for
  feeding a mempool instance. **Derived from `pools.json`; edit that one, then
  mirror the change here.**

## Listing your pool

Open a pull request that appends one object to the `pools` array in
`pools.json`. Nothing else needs to change — the page is generated from that
file at load time.

```json
{
  "name": "your-pool",
  "operator": "you or your org",
  "chain": "alphanet",
  "mode": "pps-classic",
  "fee_bps": 100,
  "coinbase_tag": "/yourpool/",
  "stratum_url": "stratum+tcp://pool.example.com:3334",
  "dashboard_url": "https://pool.example.com",
  "status_url": "https://pool.example.com/api/status",
  "operator_address": "bc1q...",
  "pool_btc_address": "bc1q...",
  "payout": "One sentence: what the stratum username must be, and how miners get paid.",
  "software": "simplepool",
  "contact": "you@example.com"
}
```

### Required

| Field | What it is |
| --- | --- |
| `name` | Short display name. |
| `operator` | Who runs it — an org, handle or domain. |
| `chain` | Which forknet, e.g. `alphanet`. Note bitcoind reports `main` on all of these: they are mainnet forks, so `main` is correct and not a misconfiguration. |
| `mode` | `solo` or `pps-classic`. Decides what the stratum username must be. |
| `fee_bps` | Basis points. `100` = 1%. |
| `coinbase_tag` | Exactly as it appears in your coinbase, slashes included. |
| `stratum_url` | Full `stratum+tcp://host:port` a miner can paste. |
| `operator_address` | The address taking the fee cut. |

### Optional

`dashboard_url`, `status_url`, `pool_btc_address` (`null` for solo), `payout`,
`software`, `contact`.

## Why `coinbase_tag` is the field to get right

It is the string your pool stamps into the coinbase of every block it finds, and
it is the only thing an explorer can use to attribute a block to you. If it is
wrong — or still on simplepool's `/simplepool/` default — your blocks are
credited to someone else and nothing anywhere reports an error.

Read it out of the pool that is actually running, not from memory or from your
install notes:

```sh
grep coinbase_tag /path/to/simplepool/proxy.conf
```

On simplepool specifically, the installer restores its answers from
`/etc/simplepool/install.env` on every run, so a `proxy.conf` edited by hand is
silently reverted on the next upgrade. If those two files disagree, fix the
installer answer as well — otherwise the tag you list here will stop being true
the next time the pool is updated.

## `pools-v2.json` (mempool format)

[mempool](https://github.com/mempool/mining-pools) attributes blocks from its
own list, `pools-v2.json`, in a different shape from `pools.json`. The copy here
is that upstream file verbatim, with this repo's pools appended:

```json
{
  "id": 1001,
  "name": "your-pool",
  "addresses": ["bc1q..."],
  "tags": ["/yourpool/"],
  "link": "https://pool.example.com"
}
```

The mapping is `name` → `name`, `coinbase_tag` → the single entry in `tags`, and
`dashboard_url` → `link`. `addresses` holds whichever address of yours actually
lands in the coinbase: `pool_btc_address` for a pooled payout,
`operator_address` for a solo pool that still takes a fee cut, and `[]` for a
zero-fee non-custodial pool, where nothing but the tag can identify you.

Our ids start at **1001** on purpose. Upstream ids run sequentially from 1 and
upstream is still growing, so keeping our block clear of it makes a refresh
"replace everything below id 1000 with the new upstream file" instead of a
merge conflict over an id two different pools both claim.

## House rules

* One pool per object; append rather than reordering, so diffs stay readable.
* A PR that changes another operator's entry will not be merged without their
  sign-off.
* Keep `payout` to one sentence — it is the line a miner reads before connecting.
