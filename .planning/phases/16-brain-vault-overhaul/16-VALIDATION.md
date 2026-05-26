# Validation Architecture — Phase 16: Brain Vault Overhaul

**Phase goal:** Turn the Obsidian second brain from a read-it-later pile into a leverage multiplier — TELOS-scored ingestion, spec-driven shipping from brain, and automated hygiene loops.

---

## Plan 16-01 — Fill TELOS

### Automated checks

```bash
# TELOS status
python3 -m ultra_brain --vault ~/Documents/second-brain telos 2>&1 | grep -i "status"

# Confirm sub-docs are non-empty
for f in mission quarter-goals values dont-do; do
  wc -l ~/Documents/second-brain/_system/telos/$f.md
done

# Confirm placeholder text is gone
grep -r "To be filled via" ~/Documents/second-brain/_system/telos/ && echo "FAIL: placeholder found" || echo "PASS: no placeholders"
```

### Manual checks

- [ ] Read mission.md — does the mission statement match the agreed wording from grilling session?
- [ ] Read quarter-goals.md — are G1/G2/G3 measurable (not vague)?
- [ ] Read values.md — do all four values have an in-practice rule?
- [ ] Read dont-do.md — does it explicitly state the ingest-everything-filter-later model?
- [ ] vault/_system/telos.md frontmatter shows `status: active`

### Acceptance

All automated checks pass AND all manual checkboxes ticked.

---

## Plan 16-02 — Inbox Sweep + Operating Manual

### Automated checks

```bash
# Inbox should contain only MOC.md and README.md
ls ~/Documents/second-brain/Inbox/ | grep -v "^MOC.md$" | grep -v "^README.md$" && echo "FAIL: extra files in Inbox" || echo "PASS: inbox clean"

# Archives exist
ls ~/Documents/second-brain/03-Archives/inbox-sweep-2026-05/ | wc -l

# Log entry exists
grep "inbox-sweep" ~/Documents/second-brain/_system/log.md && echo "PASS: log entry found" || echo "FAIL: no log entry"

# Operating manual exists and has required sections
wc -l ~/Documents/second-brain/_system/operating-manual.md
grep -c "##" ~/Documents/second-brain/_system/operating-manual.md
grep "Daily auto-triage" ~/Documents/second-brain/_system/operating-manual.md && echo "PASS: cadence table present" || echo "FAIL: cadence table missing"
grep "Acceptance Criteria" ~/Documents/second-brain/_system/operating-manual.md && echo "PASS: spec checklist present" || echo "FAIL: spec checklist missing"
```

### Manual checks

- [ ] Inbox is empty except MOC.md and README.md
- [ ] 03-Archives/inbox-sweep-2026-05/ contains the bulk of the ~140 items
- [ ] 02-Resources/articles/ has the AI/agent-relevant promoted items
- [ ] operating-manual.md can be skimmed in under 5 minutes
- [ ] Cadence table lists all 4 loops with autonomous vs HITL distinction
- [ ] Spec discipline checklist has the 7 required fields

### Acceptance

All automated checks pass AND all manual checkboxes ticked.

---

## Plan 16-03 — Graph Bridge + Spec Generator

### Automated checks

```bash
# Reindex bridge script is executable
test -x scripts/reindex_bridge.sh && echo "PASS: executable" || echo "FAIL: not executable"

# Bridge script exits 0
bash scripts/reindex_bridge.sh; echo "Exit code: $?"

# ARCHITECTURE.md written
ls vault/repos/ 2>/dev/null || ls ~/Documents/second-brain/repos/ 2>/dev/null

# Spec gen tests
rtk pytest tests/unit/test_spec_gen.py -q 2>&1 | tail -10

# CLI smoke run
python3 -m ultra_brain spec-gen --help 2>&1 | head -5
```

### Manual checks

- [ ] Commit something to the ultra-agents-brain repo (with hook installed) and verify ARCHITECTURE.md updates within 10s
- [ ] Run spec-gen CLI on a real vault briefing — inspect output for all 8 required sections
- [ ] Confirm spec_gen.py has no new dependencies beyond what's in requirements.txt

### Acceptance

All 4 spec_gen tests green; bridge script exits 0; ARCHITECTURE.md written on commit; CLI spec output has all required sections.

---

## Plan 16-04 — Automation Loops

### Automated checks

```bash
# TELOS scoring tests
rtk pytest tests/unit/test_telos_scoring.py -q 2>&1 | tail -10

# All existing tests still pass
rtk pytest tests/ -q 2>&1 | tail -15

# Workshop registry import clean
python3 -c "from agentos.workshop_registry import WorkshopRegistry; print('PASS: import ok')"

# Review dry-run
python3 -m ultra_brain review --dry-run --vault ~/Documents/second-brain 2>&1 | tail -20
```

### Manual checks

- [ ] Trigger monitor on a test AI/agent URL — confirm item lands in 02-Resources/ (high-relevance path)
- [ ] Trigger monitor on a test news URL — confirm item lands in 03-Archives/auto-culled/ or Inbox with low score
- [ ] Trigger weekly review — confirm Telegram message arrives with brain-health summary and two buttons
- [ ] Tap "Apply sweep" in Telegram — confirm suggested items are filed/archived
- [ ] Register a test repo via Telegram /register — confirm vault/00-Projects/<slug>/ created with all 3 files
- [ ] Re-register same repo — confirm no overwrite (idempotent)

### Acceptance

All automated checks pass AND all manual checkboxes ticked AND all existing tests remain green.

---

## Phase-level end-to-end smoke

Run after all 4 plans are complete:

```bash
# 1. TELOS active
python3 -m ultra_brain --vault ~/Documents/second-brain telos | grep -i active

# 2. Inbox clean
ls ~/Documents/second-brain/Inbox/ | wc -l  # should be 2 (MOC.md + README.md)

# 3. Operating manual
wc -l ~/Documents/second-brain/_system/operating-manual.md  # should be >= 120

# 4. Full test suite green
rtk pytest tests/ -q 2>&1 | tail -5

# 5. Spec gen works
python3 -m ultra_brain spec-gen --help
```

### Acceptance criteria (phase complete when all hold)

1. `ultra_brain telos` → TELOS status=active, all four sub-docs non-empty.
2. Inbox contains only MOC.md and README.md; original item count reconciles.
3. `_system/operating-manual.md` ≥120 lines with cadence table and spec checklist.
4. `vault/repos/<repo>/ARCHITECTURE.md` updates within 10s of a commit.
5. `spec-gen` CLI produces SPEC.md with all 8 required section headers.
6. All 4 automation loops produce expected artifacts when triggered on demand.
7. Full test suite green; no regressions.
