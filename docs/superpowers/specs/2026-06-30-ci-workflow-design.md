# CI Workflow: tests + dependency vulnerability gate — Design

**Date:** 2026-06-30
**Status:** Approved (pending spec review)

## Goal

Ensure, before anything merges into `main`, that:

1. **All tests pass.**
2. **No dependency (direct or transitive) has a known vulnerability.**
3. **Dependencies stay current** — an automated bot proposes version bumps, and those
   bumps flow through the same test + audit gate.

The repo is a uv-managed Python 3.12 CLI (`finops`). Python is pinned via `.python-version`
(`3.12.12`); `uv.lock` is committed; dev dependencies live in `[dependency-groups].dev`
(`pytest`, `pytest-mock`, `pytest-cov`). There is no existing CI, Dependabot, or pre-commit
configuration. Remote: `furio-labs/finops-cli`.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Dependency scope | Audit gate **+** auto-update bot |
| Update bot | **Dependabot** (native uv support since 2025-03; our `pyproject.toml` has version constraints, so it updates both `pyproject.toml` and `uv.lock`) |
| Vulnerability scanner | **`pip-audit`** over the resolved/transitive set exported from `uv.lock` |
| Audit on unfixable CVEs | **Blocking**, with a documented `pip-audit --ignore-vuln <ID>` escape hatch for reviewed exceptions |
| Scheduled re-audit | **Yes** — weekly, to catch CVEs disclosed against already-merged deps |
| Python versions | Single version (3.12, from `.python-version`) — no matrix; the project pins one Python |

## Architecture

Two committed files plus one-time repository settings. The settings are what actually
*block* a merge — a workflow file alone cannot. This separation is intentional and called
out explicitly so the setup is not assumed complete after the files land.

```
.github/
├── workflows/
│   └── ci.yml          # test job + audit job — the required status checks
└── dependabot.yml      # weekly uv + github-actions update PRs
```

### Unit 1 — `.github/workflows/ci.yml`

**Purpose:** Run the gate. Two independent, parallel jobs so a failure points clearly at
either "a test broke" or "a dependency is vulnerable / lock is stale".

**Triggers:**
- `pull_request` → `main` — gate every proposed merge.
- `push` → `main` — keep the default-branch status green/visible post-merge.
- `schedule` (weekly, Mondays 06:00 UTC) — re-audit `main` so newly-disclosed CVEs in
  unchanged deps surface without needing an open PR.

**Permissions:** `contents: read` (least privilege; neither job writes to the repo).

**Job `test`:**
1. `actions/checkout@v5`
2. `astral-sh/setup-uv@v6` with `enable-cache: true` (installs uv; caches the uv store
   between runs).
3. `uv sync --locked` — installs runtime + dev group from `uv.lock`. uv reads
   `.python-version` and provisions Python 3.12 as part of this step. `--locked` **fails the
   build if `uv.lock` is out of sync** with `pyproject.toml`, giving lockfile-freshness
   enforcement for free.
4. `uv run pytest` — runs the suite (135 tests today; 3 integration tests skip without
   `AZURE_TEST_SUBSCRIPTION_ID`, which is not set in CI — correct, they stay skipped).

**Job `audit`:**
1. `actions/checkout@v5`
2. `astral-sh/setup-uv@v6`
3. `uv export --frozen --no-emit-project --format requirements-txt -o requirements.txt`
   - Exports the **fully resolved, transitive** dependency set from `uv.lock`.
   - `--no-emit-project` omits the local `finops` package (not on PyPI; would otherwise
     make the audit error).
   - `--frozen` uses the lock as-is without re-resolving (lock-staleness is already the
     `test` job's responsibility).
   - Includes the dev group by default, so dev-tool CVEs are caught too. If dev-only noise
     becomes a problem, `--no-dev` narrows it to shipped deps (documented tunable, not the
     default).
4. `uvx pip-audit -r requirements.txt` — fails on any known CVE in that set.

**Escape hatch (blocking-audit policy):** when a flagged CVE has no fix available or is a
reviewed non-issue, add `--ignore-vuln <GHSA-or-PYSEC-id>` to the `pip-audit` call, with a
comment in the YAML stating the ID, date, and reason. This keeps the gate blocking by
default while preventing an unfixable transitive CVE from freezing all merges indefinitely.

### Unit 2 — `.github/dependabot.yml`

**Purpose:** Keep dependencies current; route every bump through the gate.

```yaml
version: 2
updates:
  - package-ecosystem: "uv"             # updates pyproject.toml + uv.lock
    directory: "/"
    schedule: { interval: "weekly" }
    open-pull-requests-limit: 5
  - package-ecosystem: "github-actions" # keeps checkout/setup-uv pinned-major patched
    directory: "/"
    schedule: { interval: "weekly" }
```

Each Dependabot PR triggers `ci.yml`; with branch protection in place (below), it cannot
merge unless `test` and `audit` pass.

### Unit 3 — One-time repository settings (not committable)

These make the gate *enforced* rather than merely *present*. Documented in the repo (e.g.
`docs/development.md` CI section) with exact steps, since they can't live in a tracked file:

1. **Branch protection / ruleset on `main`:** require a PR before merge; require status
   checks `test` and `audit` to pass; (optionally) require branches up to date before merge.
   Provide the `gh api` one-liner and the Settings → Branches click-path.
2. **Dependabot alerts + security updates** (Settings → Code security): GitHub then
   auto-opens fix PRs for vulnerable deps, complementing the `audit` job. (`audit` is the
   hard gate; alerts add proactive fix PRs.)

## Data flow

```
Dev opens PR → main ─┐
Dependabot opens PR ─┼─► ci.yml ─► test  (uv sync --locked → pytest)
weekly schedule ─────┘            └─ audit (uv export → pip-audit)
                                       │
                          both green ──┴── branch protection allows merge
                          either red ───── merge blocked
```

## Testing / acceptance criteria

The design is satisfied when:

1. A PR that breaks a test → `test` check is **red**, merge blocked.
2. A PR whose `uv.lock` is out of sync with `pyproject.toml` → `test` check **red**
   (`uv sync --locked`).
3. A PR introducing a dependency with a known CVE → `audit` check **red**, merge blocked.
4. A clean PR → both checks **green**, mergeable.
5. Dependabot opens weekly PRs for the `uv` and `github-actions` ecosystems, each running
   the full gate.
6. The weekly scheduled run executes `audit` against `main` and reports CVEs with no open PR.
7. After branch protection is enabled, none of the red states above can be merged to `main`.

Verification at implementation time: validate YAML syntax; confirm the jobs run on a throwaway
PR (or via `act`/`workflow_dispatch` where practical); confirm `pip-audit` flags a deliberately
vulnerable pin in a scratch branch, then is green after removing it.

## Non-goals / out of scope

- **Auto-merge** of Dependabot PRs — off initially; updates are reviewed by a human. Can be
  added later via a separate auto-merge workflow if desired.
- **Multi-Python matrix** — the project pins one Python; not needed.
- **Linting/formatting/type-check jobs** (ruff, mypy) — valuable but separate from this
  request; can be added as additional `ci.yml` jobs later.
- **Build/publish/release** automation — not in scope.
- **Configuring branch protection via code** — it is a repo setting; documented, executed
  once by a maintainer (the workflow cannot self-enforce it).

## Risks & notes

- **The files do not block merges by themselves.** Branch protection (Unit 3) is required;
  until it's set, the checks run but are advisory. This is the most common misunderstanding
  and is surfaced prominently in the docs.
- **`pip-audit` blocks on unfixable transitive CVEs.** Mitigated by the `--ignore-vuln`
  escape hatch with a documented justification.
- **Dependabot uv limitations** apply mainly when `pyproject.toml` lacks version constraints;
  ours has them, so updates to both `pyproject.toml` and `uv.lock` are expected to work.
  Security updates may occasionally run under the `pip` ecosystem label (known Dependabot
  quirk) — cosmetic, not blocking.
- **GitHub Actions minutes:** if `furio-labs/finops-cli` is private, the PR + push + weekly
  schedule runs consume Actions minutes from the org quota. Runs are short (uv-cached install
  + fast suite). The weekly cron is the only non-event-driven cost.
