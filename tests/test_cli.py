"""La ligne de commande : mêmes sorties qu'aux étapes 03 à 05.

Les commandes qui écrivent travaillent sur une copie (--data dans tmp_path).
"""

import shutil
from pathlib import Path

import pytest

from deauville.cli import main

DATA_FILE = Path(__file__).parent.parent / "data" / "festival.json"


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    copy = tmp_path / "festival.json"
    shutil.copy(DATA_FILE, copy)
    return copy


def run(capsys, *arguments: str) -> str:
    """Lance `deauville ...` et renvoie ce qui a été affiché."""
    main(["--data", str(DATA_FILE), *arguments])
    return capsys.readouterr().out


def test_summary(capsys):
    assert run(capsys) == (
        "Deauville Festival du Rire 2027\n"
        "From 2027-06-10 to 2027-06-13\n"
        "4 venues, 12 artists, 23 performances\n"
    )


def test_venues(capsys):
    lines = run(capsys, "venues").splitlines()
    assert lines[1] == "theatre-des-planches: Théâtre des Planches, 320 seats"
    assert lines[-1] == "Total: 1130 seats"


def test_programme(capsys):
    lines = run(capsys, "programme", "2027-06-11").splitlines()
    assert lines[0] == "Programme for Friday 11 June:"
    assert lines[-1] == "01:00-02:00 | Le Kiosque | After Hours (lineup)"


def test_artist(capsys):
    assert run(capsys, "artist", "max-pellerin").splitlines() == [
        "Max Pellerin",
        "Thu 10 20:30-22:30 | Grand Casino | Opening Gala (act)",
        "Fri 11 23:30-00:30 | Le Kiosque | Late Laughs (solo)",
        "Sat 12 21:00-22:40 | Théâtre des Planches | Deauville Comedy Club (host)",
        "Sun 13 20:30-22:40 | Grand Casino | Closing Gala (act)",
    ]


def test_now(capsys):
    assert run(capsys, "now", "2027-06-12T01:30").splitlines()[:2] == [
        "On stage at 2027-06-12 01:30:",
        "- After Hours at Le Kiosque, until 02:00",
    ]


def test_a_wrong_day_prints_an_error_and_exits_with_1(capsys):
    with pytest.raises(SystemExit) as stop:
        run(capsys, "programme", "June-11")
    assert stop.value.code == 1
    assert capsys.readouterr().out == (
        "Error: 'June-11' is not a day, use YYYY-MM-DD.\n"
    )


def test_add_then_cancel(capsys, monkeypatch, data_file):
    answers = iter(["Morning Coffee", "karim-benali", "la-cabane",
                    "2027-06-13T08:00", "30"])  # fmt: skip
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    main(["--data", str(data_file), "add"])
    assert capsys.readouterr().out == "Added: la-cabane-2027-06-13-0800\n"
    main(["--data", str(data_file), "cancel", "la-cabane-2027-06-13-0800"])
    assert capsys.readouterr().out == "Cancelled: Morning Coffee\n"
    assert data_file.read_bytes() == DATA_FILE.read_bytes()  # identique


def test_add_refused(capsys, monkeypatch, data_file):
    answers = iter(["Too Late", "karim-benali", "le-kiosque",
                    "2027-06-12T02:15", "30"])  # fmt: skip
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    with pytest.raises(SystemExit):
        main(["--data", str(data_file), "add"])
    assert capsys.readouterr().out == (
        "Error: Le Kiosque is busy with After Hours (2027-06-12 01:00-02:00).\n"
    )
