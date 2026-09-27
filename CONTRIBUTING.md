# Contributing

This is the **code** repo for the ktayl Underwriting & Pricing domain (board #12). Deployment config
(k8s manifests, ArgoCD apps, Kargo) lives in `minicloud-gitops` — never add k8s/Helm here. See the org
rule *Deployment repo vs code repo* (`minicloud-gitops/.claude/rules/conventions.md`).

## Branch conventions (trunk-based)

| Branch | Rules |
|---|---|
| `main` | The only deploy branch. PR required; GPG-signed commits (key `FD6D39D681DEFA34`). |
| `dev` | Working/integration branch (not a deploy track). |
| feature branches (`feat/`, `fix/`, `docs/`, `chore/`) | Short-lived → PR → `main`; auto-deleted on merge. |

> Environments ≠ branches: the platform runs `dev` + `prod` overlays, both fed from `main` (Kargo).

## Commit style

Conventional commits: `type(scope): message` — `feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `test`.
`feat:` → minor bump, `fix:` → patch, `feat!:` → major (release-please cuts releases from these).

Examples:
```
feat(appetite): add sanctioned-country decline rule
fix(api): return 404 when assessing a missing submission
docs: document the appetite reason codes
```

## PR requirements

- All CI checks must pass before merge (ruff lint + format, mypy, pytest ≥70% coverage).
- `main` PRs require GPG-signed commits.
- No `Co-Authored-By` lines — commits represent the portfolio owner's work.

## Running checks locally

```bash
python -m venv .venv && . .venv/bin/activate
make install        # pip install -e ".[test]"
make lint           # L0: ruff check + ruff format --check + mypy
make test           # L1: pytest --cov (no Docker, SQLite in-memory) --cov-fail-under=70
make fmt            # auto-fix formatting + lint
make run            # uvicorn dev server on :8000
```
