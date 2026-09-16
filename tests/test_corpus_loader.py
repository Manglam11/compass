"""Tests for compass.mining.corpus_loader.

No live corpus file or network access needed: all tests use small local
CSV fixtures written to tmp_path.
"""

from __future__ import annotations

import csv
from pathlib import Path

from compass.mining.corpus_loader import CorpusResume, _fix_mojibake, batch_resumes, load_corpus


def _write_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Category", "Resume"])
        writer.writerows(rows)


def test_fix_mojibake_reverses_double_cp1252_roundtrip():
    assert _fix_mojibake("NaÃƒÂ¯ve") == "Naïve"


def test_fix_mojibake_leaves_already_clean_text_unchanged():
    assert _fix_mojibake("Naïve Bayes classifier") == "Naïve Bayes classifier"


def test_fix_mojibake_leaves_plain_ascii_unchanged():
    assert _fix_mojibake("Built with Python and SQL") == "Built with Python and SQL"


def test_fix_mojibake_does_not_touch_true_replacement_char_loss():
    # A literal U+FFFD is genuine upstream data loss, not a decode/encode
    # mismatch -- no round trip can recover it, and the fixer must not
    # raise or otherwise mangle it further.
    text = "bullet � point"
    assert _fix_mojibake(text) == text


def test_load_corpus_fixes_mojibake_and_preserves_category(tmp_path):
    _write_csv(
        tmp_path / "corpus.csv",
        [
            ("Data Science", "Used NaÃƒÂ¯ve Bayes and SVM."),
            ("DevOps", "Built CI/CD pipelines."),
        ],
    )

    resumes = load_corpus(tmp_path / "corpus.csv")

    assert [r.category for r in resumes] == ["Data Science", "DevOps"]
    assert resumes[0].text == "Used Naïve Bayes and SVM."
    assert resumes[1].text == "Built CI/CD pipelines."


def test_resume_id_is_zero_padded_row_index(tmp_path):
    _write_csv(tmp_path / "corpus.csv", [("A", "text one"), ("B", "text two")])

    resumes = load_corpus(tmp_path / "corpus.csv")

    assert resumes[0].resume_id == "0000"
    assert resumes[1].resume_id == "0001"


def test_resume_id_width_grows_with_corpus_size(tmp_path):
    rows = [(f"cat{i}", f"text {i}") for i in range(10001)]
    _write_csv(tmp_path / "corpus.csv", rows)

    resumes = load_corpus(tmp_path / "corpus.csv")

    assert resumes[0].resume_id == "00000"
    assert resumes[10000].resume_id == "10000"


def test_batch_resumes_default_batch_size_is_ten():
    resumes = [CorpusResume(resume_id=str(i), category="c", text="t") for i in range(25)]

    batches = batch_resumes(resumes)

    assert [len(b) for b in batches] == [10, 10, 5]


def test_batch_resumes_exact_multiple_has_no_remainder_batch():
    resumes = [CorpusResume(resume_id=str(i), category="c", text="t") for i in range(20)]

    batches = batch_resumes(resumes, batch_size=10)

    assert [len(b) for b in batches] == [10, 10]


def test_batch_resumes_preserves_order():
    resumes = [CorpusResume(resume_id=str(i), category="c", text="t") for i in range(5)]

    batches = batch_resumes(resumes, batch_size=2)

    assert [r.resume_id for batch in batches for r in batch] == ["0", "1", "2", "3", "4"]


def test_batch_resumes_empty_input():
    assert batch_resumes([]) == []
