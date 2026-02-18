# Follow-up Email

Draft and send contextual follow-up emails to contacts.

## When to Use

- Weekly stale deal alert (triggered via schedule, Monday 10 AM)
- User asks to follow up with a contact
- After a meeting or call activity

## Process

1. **Gather context**:
   - Contact record (name, title, company, lifecycle stage)
   - Recent activities with this contact
   - Related deals and their status
   - Previous emails sent

2. **Determine email type**:
   - **Initial outreach**: First contact, introduce value proposition
   - **Meeting follow-up**: Summary and next steps from recent meeting
   - **Deal follow-up**: Check in on proposal or stalled deal
   - **Re-engagement**: Reach out to cold contacts with new context

3. **Draft the email**:
   - Subject line: Clear, specific, under 60 characters
   - Opening: Reference last interaction or shared context
   - Body: One clear ask or value proposition
   - Closing: Specific next step with timeline

4. **Send via email bundle** (`email__send_email`)

5. **Log an activity** with the email content and outcome

## Tone Guidelines

- Professional but conversational
- Short paragraphs (2-3 sentences max)
- One clear call to action per email
- Reference specific details to show personalization
- Never use generic templates without customization

## Rules

- Check `last_contacted` before sending — don't email someone contacted in the last 48 hours
- For stale deal alerts, prioritize by deal value
- Always BCC the CRM (record the activity)
- Max 5 follow-up emails per contact before escalating to manual review
