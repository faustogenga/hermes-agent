# Padel Multi-Cron Expansion Plan

> For Hermes: use the `job-monitoring-with-airtable` skill and keep all regional crons writing to the same Airtable table with the same deterministic dedupe rules.

**Goal:** Split the current two global padel job crons into smaller regional/language-focused crons so each run can search deeper with less prompt overload and clearer yield diagnostics.

**Current state:**
- `a75c797f9081` — `global-padel-coach-jobs-daily` at `0 8 * * *`
- `91cdbbf5d133` — `global-padel-coach-jobs-spanish-daily` at `30 8 * * *`
- Both write to the same Airtable table and already share overlap-safe dedupe guidance.

**Target architecture:**
- Replace 2 broad crons with 7 focused crons:
  - Spanish: Argentina, Spain, Other Spanish-speaking countries
  - English: United States, Asia, Europe, Rest of world
- Keep the same Airtable destination and same merge-key logic across all 7.
- Give each cron its own short Telegram summary so regional yield can be compared separately.
- Stagger schedules through the day to reduce contention and make logs easier to inspect.

---

## Region split

### Spanish family
1. `padel-jobs-spanish-argentina`
   - Scope: Argentina only
   - Query language: Spanish
   - Bias: clubs, federations, resorts, academies, LinkedIn, Indeed, direct sites, Argentinian job boards

2. `padel-jobs-spanish-spain`
   - Scope: Spain only
   - Query language: Spanish
   - Bias: Spanish federation boards, club sites, LinkedIn Spain, Spanish job boards

3. `padel-jobs-spanish-other`
   - Scope: all other Spanish-speaking countries
   - Includes: Mexico, Colombia, Chile, Peru, Uruguay, Paraguay, Ecuador, Costa Rica, Panama, Guatemala, Dominican Republic, etc.
   - Query language: Spanish
   - Exclude Argentina and Spain explicitly from prompt

### English family
4. `padel-jobs-english-us`
   - Scope: United States only
   - Query language: English

5. `padel-jobs-english-asia`
   - Scope: Asia-focused markets
   - Start with: UAE, Qatar, Saudi Arabia, Singapore, Hong Kong, Thailand, Indonesia, India, Philippines, Malaysia, Japan
   - Query language: English
   - Note: includes Middle East/Gulf markets here because many active padel job postings surface in English there

6. `padel-jobs-english-europe`
   - Scope: Europe except Spain
   - Start with: UK, France, Germany, Italy, Portugal, Netherlands, Belgium, Sweden, Denmark, Finland, Norway, Ireland, Switzerland, Austria
   - Query language: English
   - Exclude Spain explicitly so overlap stays intentional with the Spanish Spain cron

7. `padel-jobs-english-rest`
   - Scope: rest of world not covered above
   - Start with: Canada, Australia, New Zealand, South Africa, Latin America pages that surface only in English, Caribbean, remaining regions
   - Query language: English
   - Exclude US, Europe, and Asia buckets explicitly from prompt

---

## Scheduling proposal

Spread them over the day so each run gets room and results are easier to diagnose:

| Cron | Proposed schedule |
|---|---|
| Spanish Argentina | `0 6 * * *` |
| Spanish Spain | `0 8 * * *` |
| Spanish Other | `0 10 * * *` |
| English US | `0 13 * * *` |
| English Europe | `0 15 * * *` |
| English Asia | `0 17 * * *` |
| English Rest | `0 19 * * *` |

Notes:
- This keeps Europe/Spain in the morning local-time window and US later.
- All 7 do not need to run at the exact same depth every day; once stable, we can tune cadence by yield.
- If volume/noise is too high, the first optimization should be pausing or reducing the weakest bucket rather than broadening prompts again.

---

## Invariants that must stay the same

1. Same Airtable destination table for all 7 crons.
2. Same `Job Key` / canonical URL / semantic overlap dedupe rules.
3. Same exclusion of `thenet-padel.com`.
4. Same rule that existing rows can be refreshed but not counted as NEW.
5. Same post-upsert read-back discipline before naming jobs as NEW.
6. Same grounded-evidence standard and same explicit failure behavior for web-tool outages.

---

## Prompt changes per cron

For each new cron prompt:
1. Keep the current core mission, dedupe rules, Airtable destination, and output schema.
2. Replace global geography with an explicit country bucket.
3. Add explicit exclusions for countries handled by sibling crons.
4. Tailor query terms and source bias to the bucket.
5. Keep the message short and region-labeled, for example:
   - `Padel jobs (Spanish / Spain)`
   - `Padel jobs (English / US)`
6. Mention that this cron shares Airtable with sibling crons and must treat cross-region/language overlap as updates.

---

## Rollout sequence

### Phase 1: safe duplication
1. Copy the current Spanish cron into 3 new Spanish-region jobs.
2. Copy the current English cron into 4 new English-region jobs.
3. Leave the current 2 original global jobs paused only after the 7 new jobs exist.

### Phase 2: region prompt tightening
4. Edit each new job prompt with its exact region/country list and exclusions.
5. Keep all 7 on the same skill/toolset bundle as the originals.

### Phase 3: dry verification
6. Manually run one Spanish bucket and one English bucket.
7. Verify:
   - runs complete
   - Airtable upsert works
   - summary is concise
   - overlap becomes update, not duplicate

### Phase 4: cutover
8. Pause the 2 old global jobs.
9. Enable the 7 new jobs on the staggered schedule.
10. Watch the first 2 days of output for:
   - duplicate leaks
   - weak buckets
   - buckets with too-broad/noisy regions

---

## Risks / things to watch

1. **Cross-bucket duplicates**
   - Especially Spain vs Europe and Spanish-other vs English-rest.
   - Mitigation: explicit country exclusions in prompts plus unchanged shared Airtable dedupe.

2. **Uneven yield**
   - Some buckets may be much richer than others.
   - Mitigation: tune schedule frequency after 3–5 days of data.

3. **Prompt drift**
   - If one cron loses an exclusion or Airtable rule, duplicates/noise rise.
   - Mitigation: derive all 7 from the same base template and only vary region-specific sections.

4. **Runtime cost / token burn**
   - 7 crons cost more than 2.
   - Mitigation: tighter scope should improve per-run efficiency and job quality; later reduce low-yield buckets if needed.

---

## Recommended next action

Implement the split by:
1. creating 7 new jobs,
2. pausing the 2 old global jobs,
3. running 2 manual smoke tests,
4. then letting the full staggered schedule take over.

## Current recommendation

Yes — this split is a good idea.
It matches the existing multilingual-expansion pattern, should let each run search deeper, and should make results easier to debug and compare by region.
