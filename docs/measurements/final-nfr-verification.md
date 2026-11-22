# Final NFR verification

Scope: measured `main` commit `06ec2f59acfdcbb68d3ea437d42b16279eeeb976`, dated Nov 22 2026, role E (evidence owner). Only the cases measured below are claimed; all other NFR cases remain as previously recorded.

## NFR-001 / NFR-002 — API latency and token consumption (synthetic fixed-prompt session)

Measured with `python -m scripts.measure_latency --n 20` using the default probe against the school gateway model `CS5351/DeepSeek-V4-Flash` (real gateway).

- Attempts: 20, all succeeded, 0 failures.
- Latency, nearest-rank: p50 = 2422.222 ms, p95 = 2850.720 ms, max = 3072.404 ms.
- Interpretation limit: this was one repeated fixed input, not a general workload; the figures are not a population-wide latency guarantee.

### Token accounting (same 20 rows)

The same 20 rows were analysed with `src.report_tokens` and independent counts.

- 20 unique request IDs, 20 unique call IDs, 1 process session.
- 20 gateway calls reported `complete`; 0 partial, 0 missing, 0 `not_called`.
- Per request: 125 input, 12 output, 137 total.
- Per session: 2500 input, 240 output, 2740 total.

These are observed descriptive statistics; the requirements set no approved numerical budgets for this case.

## NFR-003 — Error-path robustness

Real extract error paths exercised with a fake transport: missing config, request timeout, HTTP 503, malformed envelope, and invalid model JSON. Result: 5 passed.

Hosted offline suite: 237 passed — [job 137082809298](https://github.com/Felix-Free/AI-Finance-Assistant/actions/runs/44981512747/job/137082809298).

## NFR-004 — Secret scanning

`python .github/ci_checks.py secret-scan` was run both locally and in hosted CI. Zero pattern matches in eligible tracked readable files; `.env` is ignored and only `.env.example` is tracked among these names. This is not a guarantee against every possible secret or against committed history. Hosted CI: [job 137082809410](https://github.com/Felix-Free/AI-Finance-Assistant/actions/runs/44981512747/job/137082809410).

## NFR-005 / NFR-006 — Deterministic validation and logging coverage

Synthetic OFFLINE run using genuine `pipeline.process`, real validation and JSONL writers, with only the model transport mocked. Eight isolated fresh ledgers, in order: food, transport, shopping, entertainment, housing, utilities, health, other.

For category i (1..8), cap 100, the sequence submitted was `(i, category)`, `(0, category)`, `(1, bad-category)`, `(1.234, category)`, `(100-i, category)`, `(0.01, category)`.

- Exactly 16 accepted records; independently rechecked: positive finite amounts with ≤2 decimals, allowed categories, running `Decimal` sums, stored cap and totals.
- 0/16 accepted records failed re-validation (0%).
- 48/48 attempts produced exactly one call row (100%).
- 16/16 accepted records joined by `call_id` (100%).
- 32/32 rejected records joined by `call_id` and `request_id` with exact reason (100%); rejected IDs absent from the ledger.
- Rejections: 16 amount, 8 category, 8 budget.
- Uniqueness checked per ledger.

Interpretation limit: this measures sample coverage, not a population-wide proof. NFR-005 and NFR-006 have no approved numerical thresholds.

## NFR-007 — Mutation coverage of invariants

Real test nodes `test_inv001_rejects_negative_amount`, `test_inv002_rejects_unknown_category`, `test_inv003_rejects_one_cent_over_budget` were run against disposable copies of the current source, disabling one relevant conditional at a time: each control passed, and each corresponding mutant failed with `DID NOT RAISE`. Result 3/3 = 1.0. The threshold 1.0 is listed as pending confirmation; requirements were not modified and no team sign-off is claimed.

## Live sample rows

Sequential requests in one process session. Sample numbers replace the request and call IDs. Latencies are rounded to 0.001 ms.

| Sample | Latency (ms) | Input tokens | Output tokens | Total tokens |
|---:|---:|---:|---:|---:|
| 1 | 2850.720 | 125 | 12 | 137 |
| 2 | 3072.404 | 125 | 12 | 137 |
| 3 | 2582.893 | 125 | 12 | 137 |
| 4 | 2488.130 | 125 | 12 | 137 |
| 5 | 2413.632 | 125 | 12 | 137 |
| 6 | 2378.222 | 125 | 12 | 137 |
| 7 | 2473.521 | 125 | 12 | 137 |
| 8 | 2390.111 | 125 | 12 | 137 |
| 9 | 2381.100 | 125 | 12 | 137 |
| 10 | 2351.255 | 125 | 12 | 137 |
| 11 | 2507.206 | 125 | 12 | 137 |
| 12 | 2331.299 | 125 | 12 | 137 |
| 13 | 2362.139 | 125 | 12 | 137 |
| 14 | 2422.222 | 125 | 12 | 137 |
| 15 | 2485.588 | 125 | 12 | 137 |
| 16 | 2296.957 | 125 | 12 | 137 |
| 17 | 2472.942 | 125 | 12 | 137 |
| 18 | 2408.701 | 125 | 12 | 137 |
| 19 | 2651.594 | 125 | 12 | 137 |
| 20 | 2830.674 | 125 | 12 | 137 |

### Example joins from the offline sample

Selected fields from the food ledger (IDs replaced consistently per attempt).

```json
{
  "accepted": {
    "call": {
      "call_id": "accepted-call_id",
      "request_id": "accepted-request_id",
      "input": "redacted:len=9",
      "raw": "redacted:len=33",
      "parsed": null
    },
    "ledger": {
      "call_id": "accepted-call_id",
      "amount": 1,
      "category": "food",
      "total": 1.0,
      "budget_limit": 100
    }
  },
  "rejected": {
    "call": {
      "call_id": "rejected-call_id",
      "request_id": "rejected-request_id",
      "input": "redacted:len=9",
      "raw": "redacted:len=36",
      "parsed": null
    },
    "review": {
      "call_id": "rejected-call_id",
      "request_id": "rejected-request_id",
      "error": "policy:budget",
      "amount": null,
      "category": null,
      "spent": null,
      "total": null,
      "review": true
    }
  }
}
```
