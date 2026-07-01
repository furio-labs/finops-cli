# CI Workflow (tests + dependency vulnerability gate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Actions CI that runs the test suite and a dependency vulnerability audit on every PR to `main`, plus Dependabot to keep dependencies current — so nothing merges to `main` with failing tests or a known-vulnerable dependency.

**Architecture:** Two committed files — `.github/workflows/ci.yml` (parallel `test` and `audit` jobs) and `.github/dependabot.yml` (weekly `uv` + `github-actions` updates) — plus documentation of the one-time repository settings (branch protection, Dependabot alerts) that actually enforce the gate. Every job uses `astral-sh/setup-uv` and runs through `uv`. The audit audits the *synced locked environment* in place rather than a requirements file, which is robust across machines.

**Tech Stack:** GitHub Actions, `astral-sh/setup-uv@v7`, `actions/checkout@v7`, uv (0.11+), `pip-audit` (via `uvx`/`uv run --with`), Dependabot v2, Python 3.12.

**Branch:** Execute on a feature branch (e.g. `ci/add-pipeline`) so the first PR exercises the new gate. Note: local `main` has diverged from `origin/main` (the earlier history rewrite has not been force-pushed); pushing this work entails that force-push — see "Maintainer steps" at the end.

## Global Constraints

- All Python/tools invoked via `uv` (`uv sync`, `uv run`) — never bare `python`/`pip`.
- Pin actions to the major-alias tag `@v7` for both `actions/checkout` and `astral-sh/setup-uv` (verified latest major aliases; Dependabot's `github-actions` ecosystem bumps them thereafter).
- Test job uses `uv sync --locked` (NOT `--frozen`) so a stale/out-of-sync `uv.lock` fails CI.
- Audit MUST pass `--skip-editable` so the local editable `finops` package (not on PyPI) is skipped.
- Branch-protection required-status-check contexts must exactly equal the job ids: `test` and `audit`. Do not set custom `name:` on these jobs (the displayed context defaults to the job id).
- Audit is **blocking**; unfixable/reviewed CVEs are silenced only via an inline-commented `pip-audit --ignore-vuln <ID>`.
- Spec of record: `docs/superpowers/specs/2026-06-30-ci-workflow-design.md`.

---

### Task 1: CI workflow — `test` + `audit` jobs

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: two status-check contexts named `test` and `audit` (consumed by branch protection in the Maintainer steps).

- [ ] **Step 1: Prove the job command sequences work locally (the "test" for the job logic)**

These are the exact commands the jobs will run. Confirm green BEFORE encoding them in YAML.

Run:
```bash
uv sync --locked
uv run pytest
uv run --with pip-audit pip-audit --skip-editable
```
Expected:
- `uv sync --locked` → exits 0 with no "lockfile out of date" error.
- `uv run pytest` → `135 passed, 3 skipped` (integration tests skip without `AZURE_TEST_SUBSCRIPTION_ID`).
- `pip-audit` → `No known vulnerabilities found`, a row showing `finops … distribution marked as editable`, exit 0.

- [ ] **Step 2: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"   # Mondays 06:00 UTC — re-audit main for newly disclosed CVEs

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      - name: Install dependencies (locked)
        run: uv sync --locked
      - name: Run tests
        run: uv run pytest

  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      - name: Install dependencies (locked)
        run: uv sync --locked
      # Audits the synced environment in place. --skip-editable omits the local
      # finops package (not on PyPI). To silence an unfixable/reviewed CVE, append
      # e.g. --ignore-vuln GHSA-xxxx-xxxx-xxxx with a comment stating ID/date/reason.
      - name: Audit dependencies for known vulnerabilities
        run: uv run --with pip-audit pip-audit --skip-editable
```

- [ ] **Step 3: Validate the YAML structure**

Note: PyYAML parses the bare key `on:` as the boolean `True` (YAML 1.1) — the check accounts for this.

Run:
```bash
uv run python - <<'PY'
import yaml
d = yaml.safe_load(open('.github/workflows/ci.yml'))
on = d.get('on', d.get(True))            # bare 'on' parses as boolean True
assert set(d['jobs']) == {'test', 'audit'}, d['jobs']
assert {'pull_request', 'push', 'schedule'} <= set(on), on
assert d['permissions'] == {'contents': 'read'}, d['permissions']
print('ci.yml structure OK')
PY
```
Expected: `ci.yml structure OK` (exit 0). If it raises `AssertionError`, fix the YAML and re-run.

- [ ] **Step 4: (Optional) Lint with actionlint if available**

Run:
```bash
command -v actionlint >/dev/null && actionlint .github/workflows/ci.yml || echo "actionlint not installed — skipping (optional)"
```
Expected: no findings, or the skip message. (actionlint is not a project dependency; do not install it just for this.)

- [ ] **Step 5: Re-run the exact job commands to confirm still green**

Run:
```bash
uv sync --locked && uv run pytest && uv run --with pip-audit pip-audit --skip-editable
```
Expected: tests `135 passed, 3 skipped`; audit `No known vulnerabilities found`; overall exit 0.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add test + dependency-audit workflow gating PRs to main"
```

---

### Task 2: Dependabot configuration

**Files:**
- Create: `.github/dependabot.yml`

**Interfaces:**
- Consumes: nothing. Produces: weekly update PRs that trigger `ci.yml` from Task 1.

- [ ] **Step 1: Create `.github/dependabot.yml`**

```yaml
version: 2
updates:
  # Python dependencies — updates pyproject.toml and uv.lock together.
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
  # Keep the workflow's action versions patched.
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

- [ ] **Step 2: Validate the YAML structure**

Run:
```bash
uv run python - <<'PY'
import yaml
d = yaml.safe_load(open('.github/dependabot.yml'))
assert d['version'] == 2, d['version']
ecos = {u['package-ecosystem'] for u in d['updates']}
assert ecos == {'uv', 'github-actions'}, ecos
assert all(u['directory'] == '/' for u in d['updates'])
assert all(u['schedule']['interval'] == 'weekly' for u in d['updates'])
print('dependabot.yml OK')
PY
```
Expected: `dependabot.yml OK` (exit 0).

- [ ] **Step 3: Commit**

```bash
git add .github/dependabot.yml
git commit -m "ci: add Dependabot for weekly uv + github-actions updates"
```

---

### Task 3: Document CI and add status badge

**Files:**
- Modify: `docs/development.md` (append a "Continuous Integration" section)
- Modify: `README.md` (add a CI badge under the title)

**Interfaces:**
- Consumes: job contexts `test`/`audit` from Task 1; the `ci.yml` workflow path for the badge URL.

- [ ] **Step 1: Append a CI section to `docs/development.md`**

Add at the end of the file:
```markdown
## Continuous Integration

`.github/workflows/ci.yml` runs on every pull request to `main`, on pushes to `main`,
and weekly (Mondays 06:00 UTC). Two jobs run in parallel:

- **test** — `uv sync --locked` (fails if `uv.lock` is out of sync with `pyproject.toml`)
  then `uv run pytest`.
- **audit** — `uv sync --locked` then `uv run --with pip-audit pip-audit --skip-editable`,
  which fails the build on any known CVE in the resolved dependency tree.

`.github/dependabot.yml` opens weekly PRs for the `uv` (Python deps) and `github-actions`
ecosystems; each PR re-runs the gate above.

### Silencing an unfixable vulnerability

If `audit` flags a CVE with no available fix (or a reviewed non-issue), append
`--ignore-vuln <GHSA-or-PYSEC-id>` to the `pip-audit` step in `ci.yml`, with a comment
stating the ID, date, and reason. Remove it once a fixed version is available.

### One-time repository settings (required to actually block merges)

The workflow files do not block merges by themselves — these GitHub settings do:

1. **Branch protection on `main`** requiring the `test` and `audit` checks. As a maintainer:
   ```bash
   cat > /tmp/protection.json <<'JSON'
   {
     "required_status_checks": { "strict": true, "contexts": ["test", "audit"] },
     "enforce_admins": true,
     "required_pull_request_reviews": null,
     "restrictions": null
   }
   JSON
   gh api -X PUT repos/furio-labs/finops-cli/branches/main/protection \
     -H "Accept: application/vnd.github+json" --input /tmp/protection.json
   ```
   (Or: Settings → Branches → Add rule → require status checks `test` and `audit`.)

2. **Dependabot alerts + security updates** (proactive fix PRs for vulnerable deps):
   ```bash
   gh api -X PUT repos/furio-labs/finops-cli/vulnerability-alerts
   gh api -X PUT repos/furio-labs/finops-cli/automated-security-fixes
   ```
   (Or: Settings → Code security → enable Dependabot alerts and security updates.)
```

- [ ] **Step 2: Add a CI badge to `README.md`**

Insert immediately under the top `# FinOps CLI` title line:
```markdown
[![CI](https://github.com/furio-labs/finops-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/furio-labs/finops-cli/actions/workflows/ci.yml)
```

- [ ] **Step 3: Sanity-check the docs render and links are well-formed**

Run:
```bash
uv run python - <<'PY'
rd = open('README.md').read()
assert 'actions/workflows/ci.yml/badge.svg' in rd, 'badge missing'
dv = open('docs/development.md').read()
assert '## Continuous Integration' in dv, 'CI section missing'
assert 'branches/main/protection' in dv, 'branch-protection steps missing'
print('docs OK')
PY
```
Expected: `docs OK` (exit 0).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/development.md
git commit -m "docs: document CI gate, badge, and required repo settings"
```

---

## Maintainer steps (manual — outside the plan's automated tasks)

These require pushing to GitHub and repo-admin rights; the agent cannot do them (no push access in this environment, and they are outward-facing). After Tasks 1–3 are committed:

1. **Push.** Pushing this branch/`main` entails the earlier history-rewrite force-push, since local `main` has diverged from `origin/main`. Confirm `git ls-remote origin` first (see the history-rewrite handoff), then push the branch and open a PR to `main`.
2. **Watch the PR.** Confirm the `test` and `audit` checks appear and pass on the PR.
3. **Enable branch protection** (Task 3 Step 1 `gh api` block) so the checks become required.
4. **Enable Dependabot alerts + security updates** (Task 3 Step 1 second `gh api` block).
5. (Optional) Trigger a manual run via the Actions tab to confirm the weekly schedule job is healthy.

## Acceptance criteria (from the spec)

1. A PR breaking a test → `test` red, merge blocked (once protection is on).
2. A PR with `uv.lock` out of sync with `pyproject.toml` → `test` red (`uv sync --locked`).
3. A PR adding a dependency with a known CVE → `audit` red, merge blocked.
4. A clean PR → both checks green, mergeable.
5. Dependabot opens weekly PRs for `uv` and `github-actions`, each running the gate.
6. The weekly scheduled run executes `audit` against `main`.
7. After branch protection is enabled, none of the red states above can merge to `main`.
