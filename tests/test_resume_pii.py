"""Tests for compass.resume_intake.pii."""

from __future__ import annotations

from compass.resume_intake.pii import find_pii


def test_finds_email_with_offset():
    text = "Contact: jane.doe@example.com for details."
    matches = find_pii(text)

    assert len(matches) == 1
    match = matches[0]
    assert match.kind == "email"
    assert match.value == "jane.doe@example.com"
    assert text[match.start : match.end] == match.value


def test_finds_indian_mobile_plain_and_spaced():
    text = "Mobile: 9876543210 or 98765 43210"
    matches = find_pii(text)

    assert [m.kind for m in matches] == ["phone", "phone"]
    assert matches[0].value == "9876543210"
    assert matches[1].value == "98765 43210"
    for m in matches:
        assert text[m.start : m.end] == m.value


def test_finds_international_phone():
    text = "Call +91 98765 43210 anytime."
    matches = find_pii(text)

    assert len(matches) == 1
    assert matches[0].kind == "phone"
    assert matches[0].value == "+91 98765 43210"
    assert text[matches[0].start : matches[0].end] == matches[0].value


def test_finds_us_style_phone():
    text = "Office: (415) 555-2671"
    matches = find_pii(text)

    assert len(matches) == 1
    assert matches[0].kind == "phone"
    assert text[matches[0].start : matches[0].end] == matches[0].value


def test_finds_linkedin_url():
    text = "Profile: linkedin.com/in/janedoe-123"
    matches = find_pii(text)

    assert len(matches) == 1
    assert matches[0].kind == "linkedin"
    assert matches[0].value == "linkedin.com/in/janedoe-123"
    assert text[matches[0].start : matches[0].end] == matches[0].value


def test_finds_github_url():
    text = "Code: https://github.com/janedoe"
    matches = find_pii(text)

    assert len(matches) == 1
    assert matches[0].kind == "github"
    assert text[matches[0].start : matches[0].end] == matches[0].value


def test_finds_other_url_not_linkedin_or_github():
    text = "Portfolio: https://janedoe.dev/portfolio"
    matches = find_pii(text)

    assert len(matches) == 1
    assert matches[0].kind == "url"
    assert text[matches[0].start : matches[0].end] == matches[0].value


def test_does_not_double_report_linkedin_as_generic_url():
    text = "See https://www.linkedin.com/in/janedoe for my profile."
    matches = find_pii(text)

    assert len(matches) == 1
    assert matches[0].kind == "linkedin"


def test_clean_fixture_reports_nothing():
    text = (
        "Experienced backend engineer with a strong record of shipping "
        "reliable systems. Led migration of the payments pipeline to a "
        "new event-driven architecture, improving throughput significantly."
    )

    assert find_pii(text) == []


def test_mailto_target_is_its_own_kind():
    text = "Reach out: mailto:jane.doe@example.com"
    matches = find_pii(text)

    assert [m.kind for m in matches] == ["mailto"]
    assert matches[0].value == "mailto:jane.doe@example.com"


def test_mailto_negative_plain_email_stays_email_kind():
    text = "Email jane.doe@example.com directly."
    matches = find_pii(text)

    assert [m.kind for m in matches] == ["email"]


def test_linkedin_shorthand_variants_detected():
    for text in [
        "linkedin/janedoe",
        "linkedin.com/janedoe",
        "www.linkedin/janedoe",
        "in/jane-doe123",
    ]:
        matches = find_pii(text)
        assert [m.kind for m in matches] == ["linkedin_shorthand"], text


def test_linkedin_shorthand_negative_common_words_files_and_versions():
    text = (
        "Comfortable specializing in/around cloud tooling. "
        "See report.pdf, built with python 3.11."
    )

    assert find_pii(text) == []


def test_github_shorthand_detected():
    text = "Code: github/janedoe"
    matches = find_pii(text)

    assert [m.kind for m in matches] == ["github_shorthand"]


def test_github_shorthand_negative_full_url_files_and_versions():
    text = "See notes.md and requirements.txt (v3.11); nothing shorthand here."

    assert find_pii(text) == []


def test_bare_domain_detected():
    text = "Portfolio: janedoe.dev"
    matches = find_pii(text)

    assert [m.kind for m in matches] == ["domain"]
    assert matches[0].value == "janedoe.dev"


def test_bare_domain_negative_filenames_and_versions():
    text = (
        "Attachments: resume.pdf, notes.md, script.py, requirements.txt, "
        "data.json, config.yaml, log.csv. Requires python 3.11."
    )

    assert find_pii(text) == []


def test_multiple_pii_classes_in_one_document():
    text = (
        "Jane Doe\n"
        "jane.doe@example.com | +91 98765 43210\n"
        "linkedin.com/in/janedoe | github.com/janedoe\n"
        "Portfolio: https://janedoe.dev\n"
    )
    matches = find_pii(text)
    kinds = sorted(m.kind for m in matches)

    assert kinds == ["email", "github", "linkedin", "phone", "url"]
    for m in matches:
        assert text[m.start : m.end] == m.value
