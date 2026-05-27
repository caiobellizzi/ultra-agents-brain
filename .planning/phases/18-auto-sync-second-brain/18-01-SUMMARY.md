---
phase: "18-auto-sync-second-brain"
plan: "18-01"
subsystem: "infra/vps-auth"
tags: [ssh, deploy-key, github, vps, manual]
dependency_graph:
  requires: []
  provides: ["vps-ssh-auth-to-second-brain"]
  affects: ["phase-18-02"]
tech_stack:
  added: []
  patterns: ["ssh deploy key", "git remote SSH"]
key_files:
  created: []
  modified: []
decisions:
  - "Deploy key preferred over PAT for repo-scoped write access on VPS"
  - "HTTPS remote replaced with SSH remote to avoid username/password prompt"
metrics:
  duration: "0 min (checkpoint — no automated work)"
  completed_date: "2026-05-27"
---

# Phase 18 Plan 01: Restore VPS↔GitHub SSH Auth — Summary

## One-liner

Manual operator checkpoint: generate ed25519 deploy key on VPS uabrain user, register on GitHub, switch second-brain remote to SSH.

## What Was Built

Nothing was built automatically. Plan 18-01 is a `type=checkpoint:manual` plan — it contains a single manual task requiring interactive VPS SSH access and GitHub deploy-key registration. The executor reached the checkpoint and returned structured instructions for the operator.

## Tasks

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Generate ed25519 deploy key + register on GitHub + switch remote | CHECKPOINT — awaiting operator | — |

## Checkpoint Instructions

The operator must:

1. SSH into VPS (as root or uabrain user at `31.97.130.253`)
2. Create `/home/uabrain/.ssh/` if missing; generate keypair at `/home/uabrain/.ssh/second_brain_deploy`
3. Add SSH config routing `github.com` to the deploy key
4. Add `github.com` to known_hosts via `ssh-keyscan`
5. SCP the pubkey locally and register it as a write-enabled deploy key via `gh repo deploy-key add`
6. Switch the VPS git remote: `git -C /srv/second-brain remote set-url origin git@github.com:caiobellizzi/second-brain.git`
7. Verify: `sudo -u uabrain git -C /srv/second-brain fetch origin main` (no auth errors)

## Deviations from Plan

None — plan executed exactly as written. This plan was designed as a manual checkpoint with no automated steps.

## Self-Check: PASSED

- No files to commit (manual checkpoint plan)
- SUMMARY.md created as required
