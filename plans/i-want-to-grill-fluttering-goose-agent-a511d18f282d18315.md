# GitHub-Native Patterns for Shared Pipelines Across Many Repos

**Research context:** A solo developer / small team (~10-20 repos, personal GitHub account) wants a single "compile a repo summary with an LLM nightly and publish it" pipeline — defined once, adopted by all repos, automatically updated when the central definition changes.

---

## 1. GitHub Reusable Workflows (`workflow_call`)

**Mechanic:** A workflow in a central (public or internal) repo sets `on: workflow_call`. Every other repo has a tiny caller file — the minimum stub is literally:

```yaml
# .github/workflows/nightly-summary.yml  (in EACH downstream repo)
jobs:
  summarize:
    uses: owner/central-workflows/.github/workflows/llm-summary.yml@main
    secrets: inherit
```

That is the *entire file*. All logic lives in `owner/central-workflows`.

**Versioning options:**

| Ref style | Example | Behaviour |
|---|---|---|
| `@main` | `...@main` | Always runs HEAD — risky, silent breakage |
| Floating tag | `...@v1` | Tag is force-pushed to latest patch; callers auto-get patches |
| Pinned semver | `...@v1.2.3` | Fully locked; update requires a PR per caller repo |
| SHA | `...@a1b2c3d4` | Maximum reproducibility, never updates silently |

**Do downstream repos auto-get updates?**
- `@main` → yes, immediately.
- Floating `@v1` → yes, whenever you force-push the `v1` tag to the new commit.
- Pinned or SHA → no; requires a Renovate/Dependabot PR in each repo.

**Private repo caveat:** A reusable workflow in a *private* repo can only be called by other workflows in *that same private repo* or by repos explicitly granted access (internal visibility). For a solo dev pattern, hosting the central workflow in a **public** repo sidesteps this entirely.

**Nesting limit:** max 10 levels deep. No limit on how many repos call the same central workflow.

**Verdict for this use case:** Reusable workflows are the core mechanism. The caller stub is ~5 lines and is essentially a one-time install.

---

## 2. GitHub Starter Workflows / Workflow Templates (`workflow-templates/`)

**Mechanic:** An org creates a public `.github` repo with a `workflow-templates/` folder. A `my-pipeline.yml` + `my-pipeline.properties.json` pair appears in the GitHub UI "New workflow" picker for all repos in that org.

**Key distinction:** Starter workflows **scaffold a copy** into the target repo. After the user clicks "Set up this workflow," the YAML is copied into `.github/workflows/` and the source org loses all control. The two files *diverge forever*.

**When this is right:**
- Bootstrapping teams that need a starting point they will customise heavily.
- One-time template repos where drift is acceptable and expected.

**When this is wrong:**
- Any "define once, stay in sync" scenario — which is exactly the use case here.

**Hybrid pattern (best of both):** Make the starter workflow template a thin caller stub that references a reusable workflow. The "copied" file is `uses: owner/central-workflows/...@v1` — tiny, unlikely to drift, and all real logic is still centrally managed.

**Personal account limitation:** Starter workflow templates in the org `.github` repo are visible only in the UI when the org has the feature. For a personal account (not an org), this UI surface does not exist. A personal user *can* still share reusable workflows publicly — the template picker is just not available.

---

## 3. Organization-Level Required / Enforced Workflows via Rulesets

**Mechanic:** An org admin defines a "Required Workflow" in repository rulesets. All PRs across selected repos must pass that workflow before merging — **no per-repo YAML file needed**.

**Plan requirement:** **GitHub Enterprise Cloud only.** This is not available on:
- Personal accounts (Free or Pro)
- Org Free tier
- Org Team plan (confirmed user reports of exclusion)

As of the most recent changelog (June 2025), org rulesets reached GA for **Team plan** for branch protection rules, but the "require workflow" piece inside rulesets remains Enterprise Cloud only.

**For a solo dev on a personal or Team-plan account:** This feature is a dead end. Do not rely on it.

**Trigger limitation:** Required workflows fire on `pull_request` and `pull_request_target` only — not `schedule`. A nightly summary pipeline is schedule-triggered, so required workflows wouldn't apply to it anyway even if you had Enterprise.

---

## 4. Composite Actions vs. Reusable Workflows

| Dimension | Composite Action | Reusable Workflow |
|---|---|---|
| Abstraction level | Wraps **steps** (used inside a job) | Wraps **jobs** (used at job level) |
| Secrets | ❌ Cannot use secrets | ✅ Can accept secrets |
| Runner spec | Inherits caller's runner | Declares its own runner |
| Nesting | Up to 10 levels | Cannot nest reusable workflows |
| Marketplace publishing | ✅ Yes | ❌ No |
| Visibility in logs | Single step in caller | Own job, full log expansion |
| Private repo access | Same cross-repo limits | Same cross-repo limits |

**For the nightly LLM summary use case:**
- The pipeline needs secrets (LLM API key), specifies its own runner, and benefits from clear job-level logs.
- **Use a reusable workflow** — not a composite action.
- Composite actions make sense for sub-steps *within* the central reusable workflow (e.g., a "call LLM" step extracted as a composite action so it can also be used standalone).

**"Define once, version-pinned, consume everywhere" ergonomics:** Reusable workflows win. Composite actions require publishing per-action `action.yml` files and tagging individual action repos — more setup, but more Marketplace-discoverable.

---

## 5. Keeping N Repos' Caller Stubs in Sync

The problem: after the initial adoption, how do you propagate changes to 50 caller stubs (e.g., bumping `@v1` → `@v2` when there's a breaking change)?

### Option A: Floating tags (`@v1` strategy)

Force-push the `v1` tag to the new commit after every backward-compatible release. All callers using `@v1` get it with zero changes to their repos. This is the **best approach for non-breaking updates** — zero propagation work.

For *breaking* changes, you bump to `@v2`, and then you do need to update callers. But breaking changes to a nightly LLM pipeline should be rare.

### Option B: Renovate Bot

Renovate scans `.github/workflows/` in every repo it manages and opens a PR when the referenced action/workflow has a newer version. Configure once in a `renovate.json` preset that all repos inherit:

```json
// renovate.json in central-config repo
{
  "extends": ["config:base"],
  "github-actions": { "enabled": true },
  "automerge": true,
  "automergeType": "pr"
}
```

Repos then add `"extends": ["github>owner/central-config"]` to their own `renovate.json`. Version bumps arrive as auto-merged PRs — zero human toil for patch/minor bumps.

**Self-hosted Renovate:** Run Renovate once as a GitHub Action in a dedicated `renovate-runner` repo on a schedule (every 15 minutes or nightly). Set `RENOVATE_TOKEN` to a PAT with read/write access to all target repos. One job, governs all repos.

### Option C: `multi-gitter` for one-off propagation

When you need to bulk-push a file change to N repos (e.g., initial adoption rollout, or a migration from `@v1` to `@v2`):

```bash
# Install: brew install multi-gitter
multi-gitter run ./add-caller-stub.sh \
  --user yourhandle \
  --branch add-nightly-summary \
  --pr-title "Add nightly LLM summary workflow" \
  --pr-auto-merge
```

`add-caller-stub.sh` simply copies the 5-line caller YAML into `.github/workflows/` if it does not already exist. PRs are opened across all your repos simultaneously; `--pr-auto-merge` merges them once CI is green.

### Option D: `actions-template-sync` / `repo-file-sync-action`

For keeping specific files (including the caller stub YAML) in sync across repos, `Redocly/repo-file-sync-action` or `AndreasAugustin/actions-template-sync` open PRs in target repos whenever the source changes. Requires a `sync.yml` config listing which files go where.

**Verdict for propagation:**
- Day-to-day: floating `@v1` tags — zero work.
- Version upgrades across repos: Renovate with shared preset + automerge.
- Initial rollout to all repos: `multi-gitter` one-shot.

---

## 6. Fan-In to a Central Knowledge Vault

The per-repo pipeline produces a `SUMMARY.md` (or `LLMS.md`). A central vault repo aggregates them. Three sub-patterns:

### Pattern A: Push from each repo (webhook push)

Each repo's nightly workflow, after generating the summary, calls:

```yaml
- name: Push summary to vault
  uses: actions/checkout@v4
  with:
    repository: owner/vault
    token: ${{ secrets.VAULT_PAT }}
    path: vault
- run: |
    cp SUMMARY.md vault/summaries/${{ github.repository_owner }}-${{ github.event.repository.name }}.md
    cd vault && git add . && git commit -m "chore: update $REPO summary" && git push
  env:
    REPO: ${{ github.repository }}
```

**Problem:** concurrent pushes from 10-20 repos running the same nightly schedule will race → push failures from merge conflicts. Needs retry logic or staggered cron times.

**Mitigation:** Stagger cron schedules per repo (or use `schedule: cron: "0 2 * * *"` in the central workflow with a `matrix` offset), or push to a branch per repo and let a merge job consolidate.

### Pattern B: Pull aggregation from vault (scheduled API fetch)

A single workflow in the vault repo runs nightly *after* all source repos have completed. It calls the GitHub API to download the latest artifact or reads a well-known file path from each source repo:

```yaml
# In owner/vault: .github/workflows/aggregate.yml
on:
  schedule:
    - cron: "0 4 * * *"  # 2h after source repos run at 0 2 * *
jobs:
  aggregate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Fetch all summaries
        run: |
          for repo in repo-a repo-b repo-c; do
            gh api repos/owner/$repo/contents/SUMMARY.md \
              --jq '.content' | base64 -d \
              > summaries/$repo.md
          done
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - run: git add . && git commit -m "chore: nightly aggregate" && git push
```

**Advantage:** No two-writer conflict — only the vault workflow writes to vault. This is the cleanest architecture.

**Disadvantage:** Two-hour lag (or requires knowing when all source jobs finish). Fine for a daily knowledge base.

### Pattern C: Artifact upload + download pattern

Each source repo uploads its summary as a workflow artifact. A central vault workflow uses `dawidd6/action-download-artifact` (or the GitHub API) to pull artifacts from other repos' latest workflow runs.

**Problem:** Artifacts are ephemeral (90-day retention by default) and require knowing the run IDs or workflow names. More plumbing than Pattern B for this use case.

**Recommended:** Pattern B (pull aggregation). The vault repo is the single writer; it pulls from each source repo's committed `SUMMARY.md` on a schedule offset from the source runs. No conflict risk, no PAT needed for writes (vault workflow writes to its own repo using `GITHUB_TOKEN`), and only one PAT (read-only) needed to read source repos.

---

## Final Architecture: Define-Once, Adopt-Everywhere, Stay-Updated

### Setup (one time)

1. **Create `owner/central-workflows`** (public repo):
   - `.github/workflows/llm-summary.yml` — the full pipeline: checkout, call LLM API with repo content, write `SUMMARY.md`, commit back.
   - Tagged with `v1` (floating) and `v1.0.0` (pinned).

2. **Create `owner/vault`** (public or private repo):
   - `.github/workflows/aggregate.yml` — scheduled at `0 4 * * *`, fetches `SUMMARY.md` from every source repo's default branch via GitHub API, commits them all.

3. **Create `owner/renovate-runner`** repo:
   - Runs self-hosted Renovate nightly with a PAT covering all repos. Shared preset auto-merges patch/minor action version bumps.

### Adoption per repo (one time, automated via multi-gitter)

Each source repo gets one file committed via `multi-gitter`:

```yaml
# .github/workflows/nightly-summary.yml
name: Nightly LLM Summary
on:
  schedule:
    - cron: "0 2 * * *"
  workflow_dispatch:
jobs:
  summarize:
    uses: owner/central-workflows/.github/workflows/llm-summary.yml@v1
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
```

Secrets (`LLM_API_KEY`) are added to each repo or — if using a GitHub org — set at org level and inherited.

### Staying in sync (ongoing, zero work)

- Backward-compatible updates to the central workflow → force-push `v1` tag → all callers pick it up on next run. No PRs needed.
- Breaking changes → bump to `@v2`, use `multi-gitter` or Renovate to open PRs across repos.
- Vault aggregation → runs independently, always fresh, no conflict risk.

---

## Quick Reference: Feature Gating for Solo/Personal Accounts

| Feature | Personal account | Org Free/Team | Org Enterprise |
|---|---|---|---|
| Reusable workflows | ✅ (from public repos) | ✅ | ✅ |
| Starter workflow templates | ❌ (no org) | ✅ | ✅ |
| Required workflows (rulesets) | ❌ | ❌ | ✅ |
| Renovate self-hosted | ✅ | ✅ | ✅ |
| multi-gitter | ✅ | ✅ | ✅ |

---

## Sources

- [Reuse Workflows — GitHub Docs](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
- [Reusing Workflow Configurations — GitHub Docs](https://docs.github.com/en/actions/concepts/workflows-and-actions/reusing-workflow-configurations)
- [How to properly version reusable workflows? — GitHub Community Discussion #30049](https://github.com/orgs/community/discussions/30049)
- [Best Practices for Reusable Workflows — Incredibuild](https://www.incredibuild.com/blog/best-practices-to-create-reusable-workflows-on-github-actions)
- [How to Use Reusable Workflows in GitHub Actions — OneUptime](https://oneuptime.com/blog/post/2025-12-20-github-actions-reusable-workflows/view)
- [GitHub Actions — Reusable Workflows vs. Custom Actions — jfagerberg.me](https://jfagerberg.me/blog/2025-10-17-reusable-workflows-custom-actions/)
- [Composite Actions vs Reusable Workflows — DEV Community](https://dev.to/n3wt0n/composite-actions-vs-reusable-workflows-what-is-the-difference-github-actions-11kd)
- [Enforcing code reliability by requiring workflows with GitHub repository rules — GitHub Blog](https://github.blog/enterprise-software/ci-cd/enforcing-code-reliability-by-requiring-workflows-with-github-repository-rules/)
- [Requiring workflows with Repository Rules is GA — GitHub Community Discussion #69595](https://github.com/orgs/community/discussions/69595)
- [Organization rulesets now available for GitHub Team plans — GitHub Changelog (June 2025)](https://github.blog/changelog/2025-06-16-organization-rulesets-now-available-for-github-team-plans/)
- [Automated Dependency Updates for GitHub Actions — Renovate Docs](https://docs.renovatebot.com/modules/manager/github-actions/)
- [Running Renovate as a GitHub Action (No PAT) — Chainguard](https://www.chainguard.dev/unchained/running-renovate-as-a-github-action)
- [multi-gitter — GitHub](https://github.com/lindell/multi-gitter)
- [actions-template-sync — GitHub Marketplace](https://github.com/marketplace/actions/actions-template-sync)
- [repo-file-sync-action — GitHub](https://github.com/Redocly/repo-file-sync-action)
- [action-template-repository-sync — GitHub](https://github.com/ahmadnassri/action-template-repository-sync)
- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Using an LLM in GitHub Actions — Tony Baloney](https://tonybaloney.github.io/posts/using-llm-in-github-actions.html)
- [GitHub Actions: Pushing Artifacts to any Repository — Medium](https://savindi-wijenayaka.medium.com/github-actions-pushing-artifacts-to-any-repository-44e302fa24ba)
- [Use git tags and loose versioning for reusable workflows — gist](https://gist.github.com/brianjbayer/2ff33c37fd6ec24326651e64202c5681)
