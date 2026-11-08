# Narration status (branch m2-narration, 2026-11-07)

## Phase A: report-voice narration (done)

- `driftwatch/agents/narration.py` (new): narrator facts computed in code, the fixed sentences,
  and the guard (`check_text`, `banned`).
- `fallbacks.narrate` builds the template from those sentences; `graph.narrator` sends the facts
  and sentences to the LLM, checks its text, retries once on a guard hit, then uses the template.
  Every attempt and the narration facts are in the narrator's trace payload.
- The closing sentence is now "Rating confidence N/100 (Band)." (the triage `score_display`
  "Trust score ..." is unchanged, so the console is unaffected).
- Cap raised from 120 to 200 words. Bare symbols (`%`, `=`, `×`) don't count as words.

### Things to know
- **Helene is never named for the three sites.** The rule is "change date within 30 days after
  2024-09-27". Newport's change date is 2024-10-28, which is 31 days after, so Newport uses its
  flood context instead ("The largest flow measured between the 2024-08-19 and 2024-10-28 visits
  was 91,700 cfs on 2024-09-28."). Hepco (2024-12-17) and Asheville (2025-07-23) fall well
  outside. A synthetic test covers the Helene branch.
- The 15-point check: Newport -47.8 % vs -42.2 % (agrees), Hepco -30.9 % vs -25.6 % (agrees),
  Asheville +9.5 % vs +46.2 % (does not back up).
- Field note picked: the note at the change visit if it has a fixed meaning, else the first
  "control changed" note, else the latest note with a meaning. Only Fill / Scour / Debris have a
  meaning; other notes (Vegetation, Submerged, Clear) produce no note sentence.
- "Lists of three adjectives" is a heuristic (three comma-listed words with adjective suffixes).
  A spaced hyphen is allowed because field notes are written "Debris - Light".
- `make test` / `make demo` were run from the worktree with
  `PY=..\AIHackathon\.venv\Scripts\python.exe` (the worktree has no venv of its own).

## Phase B: cached event context

(pending)

## LLM=gemini narrations

(pending)
