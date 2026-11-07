You write the finding for a **utility manager** who uses this river gauge's flow numbers. They are smart but not a hydrologist.

**Do not mention anything not in facts; do not describe mechanisms (washed out, lowered the bed); say what the data shows.** You may name the team's cause (e.g. "fill", "a datum change") but do not explain how it happened.

Write `text`: at most **120 words**, plain English, no jargon, no bullet points, no headings. Cover, in this order:
1. **What's wrong** — how far off the measurements are and since when. If nothing is wrong, say the gauge can be trusted.
2. **How sure we are** — the most likely cause and the confidence, in words. If the reviewer (skeptic) changed the first answer, say so in one short clause. If an objection is still unresolved, say the cause is unconfirmed.
3. **What to do next** — one concrete action.
4. **The score** — end with the `score_display` sentence exactly as given (e.g. "Trust score 24/100 (Stale).").

**Direction — use the given words verbatim, never work it out yourself.** The facts give `direction_phrase` ("above the rating" or "below the rating") and `published_flows` ("too high" or "too low"), plus `off_by_pct`, an unsigned size. Write "recent field measurements sit {off_by_pct} % {direction_phrase}, so published flows are about that much {published_flows}" (wording around it may vary; those two phrases may not). Never infer direction from a number's sign or from any other field.

Say "confident" only when the ranker's confidence is 0.8 or higher; otherwise say "likely" or "uncertain".

**Trusted gauge** (the team's final call is null): say it can be trusted, give the recent median residual with its direction, and you may use `days_since_last_visit`, `n_visits_last_12_months` and `latest_control_note` exactly as given. Nothing else.

**If the team's final call has a `disagreement`**, write it in this order instead of step 2: the best guess (cause and confidence, say "uncertain"), then the field note quoted verbatim with its date, then why they disagree (from `why_they_disagree`, in plain words), then the sentence "Double-check: " followed by `recommended_check`. Then the score sentence.

Also return the parts of what you wrote:
- `direction`: the `direction_phrase`, verbatim.
- `confidence_word`: "confident", "likely" or "uncertain" (use "uncertain" for a disagreement; "n/a" for a Trusted gauge).
- `cause_or_disagreement`: your cause sentence, or the disagreement sentences.
- `action`: your next-step sentence.
- `score_sentence`: the `score_display` sentence, verbatim.

Tone: calm, direct, like a good engineer briefing a manager. Never claim more certainty than the confidence given. Do not invent numbers.
