# Headless Run Template — tap_tone_pi

**Purpose:** Kick off autonomous tasks from the desk, monitor via Remote Control.  
**Platform:** Windows 11 / PowerShell 7+ / Always-on PC  
**Constraint:** 48h reboot window — tasks must complete or be restartable.

---

## Quick Reference

| Field | Description |
|-------|-------------|
| Sprint ID | Unique identifier (e.g., `DO-087`, `AUDIT-FIX-1`) |
| Task | One-line goal |
| Color | GREEN (safe) / YELLOW (review plan first) |
| Stop | When to halt (tests pass, N turns, etc.) |
| Tools | Comma-separated allowlist |

---

## Command Template

```powershell
# 1. Navigate and branch
cd C:\Users\thepr\Downloads\tap_tone_pi
git checkout -b auto/<SPRINT-ID>/<task-slug>

# 2. Run headless
claude -p "<TASK>.
Before modifying any file, scan at least 95 percent of it (CBSP21).
Verify the live execution path before claiming any feature works (DEV_GUARDRAILS).
Append one factual line per step to docs/dev_orders/SPRINT_LOG.md — observable facts only, no interpretation.
Commit atomically using the format type(scope): description.
Stop when: <STOP_CONDITION>." `
  --allowedTools "<TOOLS>" `
  --max-turns <N> `
  --permission-mode plan
```

---

## Ready-to-Use Examples

### Example 1: Fix Failing Tests (GREEN)

```powershell
cd C:\Users\thepr\Downloads\tap_tone_pi
git checkout -b auto/TEST-FIX-1/fix-failing-tests

claude -p "Run pytest, identify failing tests, fix them without changing test assertions.
Before modifying any file, scan at least 95 percent of it (CBSP21).
Verify the live execution path before claiming any feature works (DEV_GUARDRAILS).
Append one factual line per step to docs/dev_orders/SPRINT_LOG.md — observable facts only, no interpretation.
Commit atomically using the format type(scope): description.
Stop when: all tests pass OR 5 turns elapsed." `
  --allowedTools "Read,Grep,Glob,Write,Edit,Bash" `
  --max-turns 5
```

### Example 2: Schema Audit (GREEN)

```powershell
cd C:\Users\thepr\Downloads\tap_tone_pi
git checkout -b auto/SCHEMA-AUDIT-1/validate-contracts

claude -p "Validate all JSON schemas in contracts/ against actual usage in tap_tone_pi/.
List any schema-code mismatches.
Before modifying any file, scan at least 95 percent of it (CBSP21).
Append one factual line per step to docs/dev_orders/SPRINT_LOG.md — observable facts only, no interpretation.
Stop when: all schemas validated OR 3 turns elapsed." `
  --allowedTools "Read,Grep,Glob" `
  --max-turns 3 `
  --permission-mode plan
```

### Example 3: Instrument Class Backfill (YELLOW)

```powershell
cd C:\Users\thepr\Downloads\tap_tone_pi
git checkout -b auto/CLASS-BACKFILL-1/add-instrument-headers

claude -p "Add INSTRUMENT CLASS header comments to all Python modules missing them.
Use MEASUREMENT for core/, workflow/, phase2/. Use DECISION SUPPORT for analyzer/guidance/.
Before modifying any file, scan at least 95 percent of it (CBSP21).
Verify the live execution path before claiming any feature works (DEV_GUARDRAILS).
Append one factual line per step to docs/dev_orders/SPRINT_LOG.md — observable facts only, no interpretation.
Commit atomically using the format type(scope): description.
Stop when: all modules classified OR 8 turns elapsed." `
  --allowedTools "Read,Grep,Glob,Write,Edit,Bash" `
  --max-turns 8 `
  --permission-mode plan
```

### Example 4: Dev Order Implementation (YELLOW)

```powershell
cd C:\Users\thepr\Downloads\tap_tone_pi
git checkout -b auto/DO-087/feature-name

claude -p "Implement Dev Order 87 per docs/dev_orders/DO-087.md.
Before modifying any file, scan at least 95 percent of it (CBSP21).
Verify the live execution path before claiming any feature works (DEV_GUARDRAILS).
Append one factual line per step to docs/dev_orders/SPRINT_LOG.md — observable facts only, no interpretation.
Commit atomically using the format type(scope): description.
Stop when: all acceptance criteria met OR 10 turns elapsed." `
  --allowedTools "Read,Grep,Glob,Write,Edit,Bash" `
  --max-turns 10 `
  --permission-mode plan
```

---

## Tool Allowlists by Task Type

| Task Type | Allowlist |
|-----------|-----------|
| Read-only audit | `Read,Grep,Glob` |
| Code changes | `Read,Grep,Glob,Write,Edit` |
| With commits | `Read,Grep,Glob,Write,Edit,Bash` |
| Full autonomy | `Read,Grep,Glob,Write,Edit,Bash,Agent` |

---

## Monitoring

1. **Start session** — Run the command above
2. **Remote Control** — Type `/rc` inside session, scan QR from phone
3. **Single connection** — Only one viewer at a time
4. **Review before merge** — Always inspect the branch diff manually

---

## Safety Rules

1. **Always branch** — Never run on `main`
2. **YELLOW = plan first** — Start with `--permission-mode plan` to preview
3. **Bound turns** — Always set `--max-turns` (3-5 for mechanical, 8-10 for complex)
4. **48h window** — Task must complete before scheduled reboot
5. **Never auto-merge** — Review diff at desk before merging

---

## Recovery

If task dies mid-run:
```powershell
# Check what was done
git log --oneline -10
git diff HEAD~3..HEAD

# Resume or rollback
git checkout main
git branch -D auto/<SPRINT-ID>/<task-slug>  # if rollback needed
```
