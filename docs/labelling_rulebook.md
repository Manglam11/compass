# Compass — Labelling Rulebook v1

**Binds to:** taxonomy `0.5.1` · label schema `label_version: 1`
**Rule:** if a resume raises a case not covered here, STOP labelling, add the rule, then continue. Never decide it in your head.

---

### R1 — Section headings are `ambiguous`, always

A skill appearing **only** as a section heading is never `present`.

> "**MLOps & Serving**" as a heading, no MLOps work in any bullet → `mlops` in `skills_ambiguous`.
> Same heading, plus "set up model retraining pipeline" underneath → `present`.

---

### R2 — Job titles and company names do not count as evidence

A skill named only inside a title or an employer's name is `ambiguous`.

> "Python Developer Intern, DataCorp" with no Python in the bullets → `python` in `skills_ambiguous`.

Rationale: the extractor will match the title string. If you label it `present`, the model is rewarded for reading titles as claims — the same class of error as R1.

---

### R3 — Courses and certificates are `ambiguous`

Completion is not application.

> "Completed Docker for Developers (Udemy)" → `docker` in `skills_ambiguous`.
> Same line plus a containerised project → `present`.

---

### R4 — Teaching or tutoring a skill is `present`

> "Taught SQL to junior analysts" → `sql` in `skills_present`.

Rationale: you cannot teach what you cannot do. This overturns the Session 03 assumption that "taught SQL" is ambiguous — the ambiguity there is the extractor's, not the candidate's.

---

### R5 — Label the capability, never the library

If the taxonomy rolls a library into a capability, label the capability id only. If the library **is** its own skill id in `skills.yaml`, label the library.

> `seaborn` → label `data_visualisation`.
> `pandas` → label `pandas` (it is its own id).

Check `skills.yaml` before labelling any library. If unsure, the alias list decides.

---

### R6 — Never label an implied skill

Only what the resume says. No inference chains.

> "Deployed on AWS ECS", no mention of containers → label `cloud`, **not** `docker`.

Rationale: the extractor reads text, not the world. Labelling inference makes every model look bad for a miss it could never have made.

---

### R7 — `roles_fit` is capped at 3, ordered best-first

"Fits" means: **you would shortlist them for that role today.** Not "could grow into it."

Rationale: the output cap is top 5 and the metric is top-3 hit rate. A 6-role fit list makes the hit rate trivially easy to pass and hides a bad ranking.

---

### R8 — `roles_should_exclude` lists only plausible-but-wrong roles

Not every role outside `roles_fit`. Only roles a naive matcher would plausibly return — adjacent ones sharing vocabulary.

> A Data Analyst resume with Python and SQL → exclude `data_scientist`, `data_engineer`. Do **not** list `devops_mlops`.

Rationale: padding it with obvious non-fits inflates gate accuracy. The gate is only interesting on the near misses.

---

### R9 — Depth and recency are ignored in v1

One 2019 bullet and three 2026 projects both label `present`. Written down as a deliberate limitation, not an oversight.

Rationale: the extractor has no depth signal, so a depth-aware label can only be scored as a miss. Note it in the report as a v2 candidate.

---

## Labelling order (procedure)

1. Read the whole resume once before writing anything.
2. Skills first, roles second — never pick roles then reverse-engineer skills to justify them.
3. `skills_present` → `skills_ambiguous` → `roles_fit` → `roles_should_exclude` → `notes`.
4. `notes` records any judgement call, so B1.6 can tell a rule change from a mistake.
5. Never open the model output while labelling. Not once.

---

**Precedence when rules collide:** R6 (no inference) beats everything. R1/R2/R3 (ambiguous) beat R4/R5.