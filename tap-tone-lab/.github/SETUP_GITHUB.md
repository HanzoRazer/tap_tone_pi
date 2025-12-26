# GitHub Setup Instructions

Execute in this order to bootstrap milestones, labels, and issues.

## Prerequisites

- `gh` CLI authenticated
- `jq` installed
- Repository: `HanzoRazer/tap_tone_pi`

## 1. Create Milestones

```bash
# v1.0 Maintenance
gh api repos/HanzoRazer/tap_tone_pi/milestones \
  -f title="v1.0-instrumentation-maintenance" \
  -f description="Maintenance-only milestone to close remaining v1.0 baseline gaps (no feature changes)." \
  -f state="open"

# Phase 2
gh api repos/HanzoRazer/tap_tone_pi/milestones \
  -f title="phase-2-advanced-measurement" \
  -f description="Phase 2 measurement extensions: time-gated IR, roving ODS, multi-channel analysis, experimental wolf metrics." \
  -f state="open"
```

## 2. Create Labels

```bash
jq -c '.[]' .github/labels.bootstrap.json | while read -r label; do
  name=$(echo "$label" | jq -r '.name')
  color=$(echo "$label" | jq -r '.color')
  description=$(echo "$label" | jq -r '.description')

  gh api repos/HanzoRazer/tap_tone_pi/labels \
    -f name="$name" \
    -f color="$color" \
    -f description="$description" \
    >/dev/null 2>&1 || echo "Label '$name' already exists"
done
```

## 3. Import Issues

```bash
# v1.0 test fixtures (maintenance)
gh issue import .github/v1.0_test_fixtures_issue.json

# Phase 2 issues (when ready)
# gh issue import .github/phase2_issues.json
```

## Result

- 2 milestones: v1.0-instrumentation-maintenance, phase-2-advanced-measurement
- 13 labels for categorization
- Issues imported with proper milestone/label assignments
