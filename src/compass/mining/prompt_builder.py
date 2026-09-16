"""Builds the alias-mining prompt sent to the extraction LLM.

Alias mining is closed-vocabulary against the taxonomy's 59 skill_ids, the
same principle compass.extract.ollama_llm uses for extraction — but open on
phrasing: the model is asked to surface skill phrases a resume uses that
none of that skill's existing aliases already cover, or (still closed to a
genuine skill, just unmapped) a skill that matches none of the 59 ids at
all, flagged with skill_id "NEW".
"""

from __future__ import annotations

from compass.mining.corpus_loader import CorpusResume
from compass.taxonomy.models import Taxonomy

OUTPUT_SCHEMA_EXAMPLE = """[
  {"resume_id": "0000", "skill_id": "python", "quoted_phrase": "scripted in Py"},
  {"resume_id": "0000", "skill_id": "NEW", "quoted_phrase": "Snowflake", "suggested_name": "snowflake"}
]"""


def _vocabulary_block(taxonomy: Taxonomy) -> str:
    lines = []
    for skill_id in sorted(taxonomy.skills):
        skill = taxonomy.skills[skill_id]
        other_aliases = [alias for alias in skill.aliases if alias != skill_id]
        lines.append(f"{skill_id}: {', '.join(other_aliases)}")
    return "\n".join(lines)


def _resumes_block(batch: list[CorpusResume]) -> str:
    parts = []
    for resume in batch:
        parts.append(
            f"--- resume_id: {resume.resume_id} (category: {resume.category}) ---\n"
            f"{resume.text}"
        )
    return "\n\n".join(parts)


def build_mining_prompt(batch: list[CorpusResume], taxonomy: Taxonomy) -> str:
    skill_ids = sorted(taxonomy.skills)
    return f"""You are mining new alias phrasings for a fixed skill taxonomy from a batch
of resumes.

RULES:

1. CLOSED VOCABULARY. Every skill_id you report must be one of the {len(skill_ids)}
   skill_ids listed below, or the literal string "NEW" for a genuine skill
   that maps to none of them. Do not invent skill_ids other than "NEW".

2. ALREADY COVERED. Each skill_id below is followed by the aliases already
   known for it. If a resume's phrasing for that skill is already in its
   alias list (case-insensitively), do NOT report it — it is not new
   information. Only report a phrase if it is evidence of that skill but is
   NOT one of its existing aliases.

3. NEW SKILLS. If a resume names a genuine, specific skill that does not
   correspond to any of the {len(skill_ids)} skill_ids at all, report it with
   skill_id "NEW" and a suggested_name (lowercase, underscore-separated, in
   the style of the existing skill_ids).

4. QUOTE, DON'T PARAPHRASE. quoted_phrase must be the exact substring of the
   resume text that is the evidence, not a paraphrase or the skill_id.

5. OUTPUT FORMAT. A strict JSON list, nothing before or after it, no
   markdown fences. One object per finding:

{OUTPUT_SCHEMA_EXAMPLE}

   If a resume contributes no findings, it simply contributes no objects to
   the list. An empty list [] is a valid response if nothing new is found
   anywhere in the batch.

TAXONOMY ({len(skill_ids)} skill_ids — closed vocabulary, format is
"skill_id: known aliases"):

{_vocabulary_block(taxonomy)}

RESUMES:

{_resumes_block(batch)}
"""
