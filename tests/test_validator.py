import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validator import imo_check, index_reference, validate  # noqa: E402


def vessel(imo="9074729", name="Aurora Baltic", flag="PA", owner="Bluewater Holdings Ltd"):
    return {"imo": imo, "vessel_name": name, "flag": flag, "owner": owner, "carrier": "Test Line"}


def registry(imo="9074729", name="Aurora Baltic", flag="PA", owner="Bluewater Holdings Ltd", status="IN SERVICE", former=""):
    return {"imo": imo, "ship_name": name, "flag": flag, "registered_owner": owner, "status": status, "former_names": former}


def category(master, reference):
    return validate([master], index_reference([reference]))[0].category


def test_imo_check_digit():
    assert imo_check("9074729") == (True, "", "9074729")
    assert imo_check("IMO 9074729")[0]
    assert imo_check("9074728")[1] == "IMO_CHECK_DIGIT_FAILED"
    assert imo_check("907472")[1] == "IMO_WRONG_LENGTH"
    assert imo_check("211234560")[1] == "IMO_LOOKS_LIKE_MMSI"
    assert imo_check("")[1] == "IMO_MISSING"


def test_exact_match():
    assert category(vessel(), registry()) == "MATCH"


def test_prefix_and_legal_words_are_minor_differences():
    assert category(vessel(), registry(name="MV AURORA BALTIC", owner="Bluewater Holdings Limited")) in {"MATCH", "MINOR_DIFFERENCES"}


def test_renamed_vessel():
    assert category(vessel(), registry(name="Cedar Glory", former="Aurora Baltic")) == "RENAMED"


def test_scrapped_vessel():
    assert category(vessel(), registry(status="Broken Up")) == "SCRAPPED"


def test_owner_changed():
    assert category(vessel(), registry(owner="Tidewater Assets AS")) == "OWNER_CHANGED"


def test_missing_from_reference():
    assert validate([vessel()], {})[0].category == "NOT_IN_REFERENCE"


def test_duplicate_imo_in_master_list():
    results = validate([vessel(), vessel(name="Aurora Baltic II")], index_reference([registry()]))
    assert {r.category for r in results} == {"DUPLICATE_IMO"}
