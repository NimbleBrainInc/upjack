# Deal Forecasting

Analyze deal pipeline health and predict outcomes.

## When to Use

- Daily pipeline review (triggered via schedule, weekdays 9 AM)
- A deal reaches "closed-won" (triggered via hook)
- User asks for pipeline analysis or forecast

## Process

1. **Load pipeline configuration** to understand stages and expected probabilities

2. **Analyze each active deal**:
   - Days in current stage vs. `max_days` threshold
   - Activity frequency (more activity = healthier deal)
   - Value-weighted probability
   - Relationship to contact lead scores

3. **Generate insights**:
   - Total weighted pipeline value
   - Deals at risk (over max_days in stage)
   - Stage distribution analysis
   - Forecast for current month/quarter

4. **Take action on at-risk deals**:
   - Flag stale deals by adding "at-risk" tag
   - Create follow-up activities for stale deals
   - Update deal notes with analysis

## Risk Signals

| Signal | Risk Level |
|--------|-----------|
| > 2x max_days in stage | Critical |
| > 1x max_days in stage | High |
| No activity in 14 days | High |
| No activity in 7 days | Medium |
| Contact lead score < 40 | Medium |
| No next step documented | Low |

## Output Format

When generating a pipeline review, structure as:
1. Summary metrics (total deals, weighted value, avg days in pipeline)
2. At-risk deals with recommended actions
3. Forecast based on probability-weighted values
4. Recommended next steps
