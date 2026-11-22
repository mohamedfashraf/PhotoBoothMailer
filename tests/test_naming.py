"""Grouping photo files into guests, and searching guests by name."""
import pytest

import naming


@pytest.mark.parametrize("stem, key, shown", [
    ("Hana", "hana", "Hana"),
    ("Hana_1", "hana", "Hana"),
    ("Hana-2", "hana", "Hana"),
    ("Hana (3)", "hana", "Hana"),
    ("hana", "hana", "Hana"),
    ("Omnya & Fatma_1", "omnya & fatma", "Omnya & Fatma"),
    ("mohamed_ashraf_001", "mohamed ashraf", "Mohamed Ashraf"),
    ("56", "56", "56"),
    ("56_1", "56", "56"),
    ("Table 5", "table 5", "Table 5"),        # a space + number is part of the name...
    ("Table 5_1", "table 5", "Table 5"),      # ...only _1, -2, (3) mean "another photo"
    ("Ahmed 2", "ahmed 2", "Ahmed 2"),
    ("Room 101_1", "room 101", "Room 101"),
    ("IMG_0042", "img 0042", "IMG 0042"),     # unrenamed camera files never merge into one "IMG" guest
    ("محمد علي_1", "محمد علي", "محمد علي"),
])
def test_grouping(stem, key, shown):
    assert naming.guest_key(stem) == key
    assert naming.display_name(stem) == shown


def test_different_numbered_names_stay_separate():
    assert naming.guest_key("Table 5") != naming.guest_key("Table 6")
    assert naming.guest_key("Ahmed") != naming.guest_key("Ahmed 2")


def test_scan_folder(photos):
    guests = naming.scan_folder(photos)
    assert sorted(g.name for g in guests.values()) == ["Hana", "Omnya & Fatma", "Table 5", "Table 6", "محمد علي"]
    assert len(guests["omnya & fatma"].photos) == 2


def test_scan_folder_ignores_other_files(photos):
    (photos / "notes.txt").write_text("x")
    (photos / "Thumbs.db").write_bytes(b"x")
    assert len(naming.scan_folder(photos)) == 5


@pytest.mark.parametrize("query, name, at_least", [
    ("hana", "Hana", 3),
    ("HANA", "Hana", 3),
    ("omn", "Omnya & Fatma", 2),
    ("fatma", "Omnya & Fatma", 2),
    ("mohamed", "Mohammed", 1),      # small spelling differences
    ("احمد", "أحمد", 3),             # Arabic letter variants
    ("56", "56", 3),
    ("٥٦", "56", 3),                 # Arabic digits
    ("56", "Table 56", 2),
])
def test_search_finds(query, name, at_least):
    assert naming.match_score(query, name) >= at_least


@pytest.mark.parametrize("query, name", [
    ("table 56", "Table 57"),        # numbers are never "close enough"
    ("10566", "10567"),
    ("zzz", "Hana"),
])
def test_search_does_not_find(query, name):
    assert naming.match_score(query, name) == 0
