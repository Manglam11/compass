"""Detect name/skill-alias collisions between a names mapping and the taxonomy.

Redaction removes each resume's name from its own text (see
compass.resume_intake.names). If a name token also happens to be a skill
alias — or a substring of a multi-word skill alias — redacting the name
destroys that skill's extraction from that resume too (KNOWN LIMITATION,
documented in names.py). This module measures how often that happens; it
does not resolve it, since the resolution (rename the alias? special-case
the resume? accept the loss?) is a human call.

Matching mirrors compass.resume_intake.names' own tokenization: a name is
split on whitespace into individual parts, lowercased, with no further
stripping of punctuation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Collision:
    resume_id: str
    skill_id: str
    token_length: int


def find_collisions(name_map: dict[str, str], alias_index: dict[str, str]) -> list[Collision]:
    """Find name tokens that collide with a skill alias.

    A token collides with a skill if it exactly matches one of that skill's
    aliases, or if it appears as a substring of one of that skill's
    multi-word aliases (e.g. token "carlo" against alias "monte carlo").
    `alias_index` maps alias -> skill_id, as produced by
    compass.taxonomy.loader.load_taxonomy (already lowercased and
    deduplicated there).

    Each (resume_id, skill_id, token_length) triple is reported at most
    once, even if more than one token or match rule produces it. The name
    and the matched token are deliberately never included — only their
    length — since this function's output is meant to be safe to print or
    log without leaking PII.
    """
    multi_word_aliases = [alias for alias in alias_index if " " in alias]

    collisions: list[Collision] = []
    seen: set[tuple[str, str, int]] = set()

    for resume_id, name in sorted(name_map.items()):
        for raw_token in name.split():
            token = raw_token.lower()
            if not token:
                continue

            matched_skill_ids: set[str] = set()
            exact_skill_id = alias_index.get(token)
            if exact_skill_id is not None:
                matched_skill_ids.add(exact_skill_id)
            for alias in multi_word_aliases:
                if token in alias:
                    matched_skill_ids.add(alias_index[alias])

            for skill_id in sorted(matched_skill_ids):
                key = (resume_id, skill_id, len(token))
                if key not in seen:
                    seen.add(key)
                    collisions.append(
                        Collision(resume_id=resume_id, skill_id=skill_id, token_length=len(token))
                    )

    return collisions
