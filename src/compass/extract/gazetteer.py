"""Extract taxonomy skill ids from resume text via a spaCy EntityRuler gazetteer.

Uses a blank English pipeline (no model download) with case-insensitive
token patterns built from every alias of every skill in the taxonomy.
"""

from __future__ import annotations

import spacy
from spacy.language import Language

from compass.taxonomy.models import Taxonomy


def _build_patterns(taxonomy: Taxonomy, nlp: Language) -> list[dict]:
    patterns = []
    for skill in taxonomy.skills.values():
        for alias in skill.aliases:
            tokens = [token.text.lower() for token in nlp.tokenizer(alias)]
            pattern = [{"LOWER": token} for token in tokens]
            patterns.append({"label": "SKILL", "pattern": pattern, "id": skill.id})
    return patterns


def extract_skills(text: str, taxonomy: Taxonomy) -> list[str]:
    nlp = spacy.blank("en")
    ruler = nlp.add_pipe("entity_ruler")
    ruler.add_patterns(_build_patterns(taxonomy, nlp))

    doc = nlp(text)
    found_ids = {ent.ent_id_ for ent in doc.ents if ent.ent_id_}
    return sorted(found_ids)
