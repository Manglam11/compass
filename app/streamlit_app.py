"""Streamlit shell around compass.pipeline.analyse_resume.

Run with: uv run streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from compass.extract.pdf_text import InsufficientTextError
from compass.pipeline import analyse_resume

st.title("Compass")

uploaded_file = st.file_uploader("Upload a resume", type=["pdf"])

if uploaded_file is not None:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = Path(tmp.name)

        result = analyse_resume(tmp_path)

        st.write(f"Extracted text: {result.character_count} characters")

        st.subheader("Skills found")
        st.write(result.found_skills)

        st.subheader("Matched roles")
        matched_rows = [
            {
                "rank": rank,
                "role_id": role.role_id,
                "score": f"{role.score:.3f}",
                "matched_skills": ", ".join(role.matched_skills),
                "missing_skills": ", ".join(role.missing_skills),
            }
            for rank, role in enumerate(result.matched_roles, start=1)
        ]
        st.table(matched_rows)

        st.subheader("Excluded roles")
        excluded_rows = [
            {"role_id": excluded.role_id, "reason": excluded.reason.value}
            for excluded in result.excluded_roles
        ]
        st.table(excluded_rows)
    except InsufficientTextError as exc:
        st.error(str(exc))
    finally:
        if tmp_path is not None:
            os.unlink(tmp_path)
