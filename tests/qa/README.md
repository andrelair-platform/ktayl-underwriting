# QA-gate smoke harness (L4)

`smoke.py` is the **QA-gate / promotion-gate** smoke suite for ktayl-underwriting (see the platform
`qa-gate.md`). It is an adversarial end-to-end pass over the live service — all appetite outcomes, the
pricing breakdown reconciliation, validation → 4xx, 404s on every read, ordering guards, the bind happy
path, idempotent re-bind, and the bound-file lock (409 on re-assess / re-quote).

**It is NOT part of unit CI.** It needs a *running* service, so it does not run in the `test-unit` /
`test-contract` / `test-integration` jobs. It is the gate you run **after a deploy**, against the live
dev service, before promoting to prod.

## Running it

```bash
# local (a service on :8000)
make smoke
# or, against any target:
BASE_URL=https://ktayl-underwriting-dev.10.0.0.200.nip.io python tests/qa/smoke.py --insecure

# in-cluster against the live dev pod (no ingress / SSO in the way):
kubectl --context minicloud exec -i -n underwriting deploy/ktayl-underwriting -- \
  python - < tests/qa/smoke.py
```

- Reads the target from `--base-url` or `$BASE_URL` (default `http://localhost:8000`).
- `--insecure` skips TLS verification (for the self-signed minicloud CA over an ingress host).
- Prints `PASS`/`FAIL` per check and **exits non-zero if any BLOCKER check fails**, so it can gate a
  promotion in a pipeline. `[warn]` checks report but do not fail the gate.

## Dependencies

Only `httpx` (already a runtime dependency of the service) + the Python stdlib — so it runs unchanged
inside the service image via `kubectl exec`.
