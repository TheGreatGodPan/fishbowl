"""Tests for the one-command refresh: download Scryfall's file, then rebuild cards.db."""

from urllib.error import URLError

from fishbowl.data.refresh import refresh


def test_downloads_then_builds():
    calls = []
    code = refresh(
        download=lambda: calls.append("download"),
        build=lambda: calls.append("build") or 0,
    )
    assert calls == ["download", "build"]
    assert code == 0


def test_build_exit_code_is_passed_through():
    assert refresh(download=lambda: None, build=lambda: 1) == 1


def test_no_network_skips_build_and_explains(capsys):
    def offline():
        raise URLError("no network")

    built = []
    code = refresh(download=offline, build=lambda: built.append(True) or 0)
    assert code == 1
    assert built == []  # never rebuild from data we failed to refresh
    out = capsys.readouterr().out
    assert "Download failed" in out
    assert "not changed" in out


def test_unexpected_scryfall_response_skips_build():
    def bad_index():
        raise ValueError("Scryfall's bulk-data index has no 'oracle_cards' file")

    built = []
    assert refresh(download=bad_index, build=lambda: built.append(True) or 0) == 1
    assert built == []
