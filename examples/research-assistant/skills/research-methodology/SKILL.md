# Research Methodology

Systematic approach to investigating topics, evaluating sources, and synthesizing findings.

## When to Use

- A new topic is created
- Daily topic monitoring (triggered via schedule)
- User asks to research a topic or find sources

## Research Process

### 1. Topic Scoping

Before searching, understand what you're looking for:
- Read the topic's `key_questions` for specific angles
- Check existing sources and notes to avoid duplication
- Identify gaps in current coverage

### 2. Source Discovery

Use `platform:web_search` with targeted queries:
- Start broad, then narrow based on initial findings
- Search for: academic papers, industry reports, expert blogs, news articles
- Try multiple query formulations for comprehensive coverage

### 3. Source Evaluation

For each potential source:
- Assess credibility (1-5 scale per context.md guidelines)
- Check publication date for recency
- Note author credentials and potential bias
- Create a source entity with full metadata

### 4. Note Extraction

Use `platform:web_scrape` or `platform:pdf_extract` to read sources:
- Create one note per distinct insight
- Tag with appropriate `claim_type`
- Include direct quotes for key claims
- Link note to both source and topic via relationships

### 5. Synthesis

When the user asks for a report or when sufficient notes exist:
- Group notes by theme, not by source
- Identify consensus and conflicts across sources
- Highlight the strongest evidence
- Note gaps and limitations

## Daily Monitoring

For the daily schedule:
1. List all active topics
2. For each topic, search for new developments (past 24 hours)
3. If significant new information found:
   - Create source and note entities
   - Add "new-development" tag
4. Skip topics tagged "paused" or with status "archived"

## Rules

- Minimum 3 sources before generating a report
- Always include source credibility in reports
- Flag when multiple sources contradict each other
- Never present a single source's claim as established fact
