# Lead Qualification

Score and qualify new contacts based on their profile and engagement signals.

## When to Use

- A new contact is created (triggered automatically via hook)
- Nightly lead scoring refresh (triggered via schedule)
- User asks to evaluate or score a contact

## Process

1. **Gather signals** from the contact record:
   - Job title and seniority (C-suite, VP, Director = high signal)
   - Company size and industry fit
   - Email domain (corporate vs. personal)
   - LinkedIn presence
   - Existing relationships to other entities

2. **Score the contact** (0-100):
   - 80-100: Hot lead — immediate follow-up needed
   - 60-79: Warm lead — nurture with targeted content
   - 40-59: Neutral — monitor for engagement
   - 0-39: Cold — low priority

3. **Update the contact** with:
   - `lead_score`: Numeric score
   - `lifecycle_stage`: Based on score (lead, mql, sql)
   - `tags`: Add relevant tags (e.g., "hot-lead", "decision-maker")

4. **Log an activity** explaining the scoring rationale

## Scoring Rubric

| Signal | Points |
|--------|--------|
| C-suite title | +25 |
| VP/Director title | +15 |
| Manager title | +10 |
| Company size > 200 | +15 |
| Company size 50-200 | +10 |
| Corporate email domain | +10 |
| LinkedIn profile present | +5 |
| Multiple relationships | +10 |
| Recent activity (7 days) | +10 |

## Rules

- Never decrease a lead score by more than 20 points in a single update
- Always explain score changes in an activity note
- If enrichment bundle is available, use `enrich_person` before scoring
