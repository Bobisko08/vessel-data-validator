"""Check a vessel master list against a reference registry export.

For every vessel the tool:
  1. validates the IMO number (format and check digit),
  2. finds duplicate IMO numbers in the master list,
  3. looks the IMO up in the reference data and compares name, flag and owner,
  4. puts the vessel into one category that tells the team what to do next.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

NAME_THRESHOLD = 0.88
OWNER_THRESHOLD = 0.80

# Ordered from "safe to accept" to "needs a person to look at it".
CATEGORIES = [
    "MATCH",              # IMO found, name/flag/owner agree
    "MINOR_DIFFERENCES",  # found, small spelling difference only
    "OWNER_CHANGED",      # found, but registered owner differs
    "RENAMED",            # found under a new name; old name in its history
    "SCRAPPED",           # reference says the ship no longer sails
    "NOT_IN_REFERENCE",   # valid IMO, but the registry has no record (often small or niche carriers)
    "DUPLICATE_IMO",      # same IMO appears more than once in the master list
    "INVALID_IMO",        # missing, wrong length or failed check digit
]

OWNER_NOISE = {"LTD", "LIMITED", "INC", "CO", "CORP", "SA", "AS", "GMBH", "BV", "PTE", "LLC", "PLC", "THE", "SHIPPING", "AND"}


def clean(value: object) -> str:
    text = "" if value is None else str(value).upper()
    text = re.sub(r"[^A-Z0-9 ]", " ", text.replace("&", " AND "))
    return re.sub(r"\s+", " ", text).strip()


def clean_vessel_name(value: object) -> str:
    # Prefixes such as "MV" or "M/V" are not part of the name.
    return re.sub(r"^(MV|M V|MS|M S|MT|M T)\s+", "", clean(value))


def clean_owner(value: object) -> str:
    return " ".join(w for w in clean(value).split() if w not in OWNER_NOISE)


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


def imo_check(raw: object) -> tuple[bool, str, str]:
    """Return (is_valid, problem_code, imo_digits).

    An IMO number has 7 digits. The last digit is a check digit: multiply the
    first six digits by 7, 6, 5, 4, 3, 2, add them up, and the last digit of
    that sum must equal the check digit. Example: 9074729 ->
    9*7 + 0*6 + 7*5 + 4*4 + 7*3 + 2*2 = 139, last digit 9.
    """
    text = str(raw or "").strip().upper().removeprefix("IMO").strip()
    digits = re.sub(r"\D", "", text)
    if not text:
        return False, "IMO_MISSING", ""
    if len(digits) == 9:
        return False, "IMO_LOOKS_LIKE_MMSI", digits
    if len(digits) != 7:
        return False, "IMO_WRONG_LENGTH", digits
    total = sum(int(digits[i]) * (7 - i) for i in range(6))
    if total % 10 != int(digits[6]):
        return False, "IMO_CHECK_DIGIT_FAILED", digits
    return True, "", digits


@dataclass
class VesselResult:
    row: dict
    imo: str
    category: str
    notes: list[str] = field(default_factory=list)
    reference: dict | None = None


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def index_reference(rows: list[dict]) -> dict[str, dict]:
    reference = {}
    for row in rows:
        valid, _, imo = imo_check(row.get("imo"))
        if valid:
            reference[imo] = row
    return reference


def compare(row: dict, ref: dict) -> tuple[str, list[str]]:
    notes = []
    if clean(ref.get("status")) in {"BROKEN UP", "SCRAPPED", "TOTAL LOSS"}:
        return "SCRAPPED", [f"registry status: {ref.get('status')}"]

    ours, theirs = clean_vessel_name(row.get("vessel_name")), clean_vessel_name(ref.get("ship_name"))
    name_score = similarity(ours, theirs)
    former = [clean_vessel_name(n) for n in str(ref.get("former_names", "")).split("|") if n.strip()]

    if name_score < NAME_THRESHOLD:
        if any(similarity(ours, old) >= NAME_THRESHOLD for old in former):
            return "RENAMED", [f"now called {ref.get('ship_name')} (we still use {row.get('vessel_name')})"]
        notes.append(f"name differs: ours '{row.get('vessel_name')}', registry '{ref.get('ship_name')}'")

    if clean(row.get("flag")) and clean(ref.get("flag")) and clean(row.get("flag")) != clean(ref.get("flag")):
        notes.append(f"flag differs: ours {row.get('flag')}, registry {ref.get('flag')}")

    owner_score = similarity(clean_owner(row.get("owner")), clean_owner(ref.get("registered_owner")))
    if clean_owner(row.get("owner")) and owner_score < OWNER_THRESHOLD:
        return "OWNER_CHANGED", notes + [f"registry owner: {ref.get('registered_owner')}"]

    if notes or name_score < 1.0:
        return "MINOR_DIFFERENCES", notes or [f"name spelling differs slightly ({name_score:.2f})"]
    return "MATCH", []


def validate(master: list[dict], reference: dict[str, dict]) -> list[VesselResult]:
    results = []
    imo_counts = Counter(imo_check(r.get("imo"))[2] for r in master if imo_check(r.get("imo"))[0])

    for row in master:
        valid, problem, imo = imo_check(row.get("imo"))
        if not valid:
            results.append(VesselResult(row, imo, "INVALID_IMO", [problem]))
        elif imo_counts[imo] > 1:
            results.append(VesselResult(row, imo, "DUPLICATE_IMO", [f"IMO {imo} appears {imo_counts[imo]} times"]))
        elif imo not in reference:
            results.append(VesselResult(row, imo, "NOT_IN_REFERENCE", ["no registry record for this IMO"]))
        else:
            category, notes = compare(row, reference[imo])
            results.append(VesselResult(row, imo, category, notes, reference[imo]))
    return results


def write_reports(results: list[VesselResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    order = {name: i for i, name in enumerate(CATEGORIES)}
    with (out_dir / "vessel_report.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["category", "imo", "vessel_name", "flag", "owner", "carrier",
                         "registry_name", "registry_flag", "registry_owner", "notes"])
        for r in sorted(results, key=lambda r: (order[r.category], r.imo)):
            ref = r.reference or {}
            writer.writerow([r.category, r.imo or r.row.get("imo"), r.row.get("vessel_name"), r.row.get("flag"),
                             r.row.get("owner"), r.row.get("carrier"), ref.get("ship_name", ""), ref.get("flag", ""),
                             ref.get("registered_owner", ""), "; ".join(r.notes)])

    counts = Counter(r.category for r in results)
    by_carrier = defaultdict(Counter)
    for r in results:
        by_carrier[r.row.get("carrier") or "(none)"][r.category] += 1

    lines = ["# Vessel validation summary", "", f"Vessels checked: {len(results)}", "",
             "| Category | Vessels |", "|---|---|"]
    lines += [f"| {name} | {counts.get(name, 0)} |" for name in CATEGORIES]
    lines += ["", "## Carriers with the most vessels missing from the registry", ""]
    top = sorted(by_carrier.items(), key=lambda kv: -kv[1]["NOT_IN_REFERENCE"])[:5]
    lines += [f"- {carrier}: {c['NOT_IN_REFERENCE']} of {sum(c.values())}" for carrier, c in top if c["NOT_IN_REFERENCE"]]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate a vessel master list against a registry export.")
    parser.add_argument("master", type=Path, help="CSV: imo, vessel_name, flag, owner, carrier")
    parser.add_argument("reference", type=Path, help="CSV: imo, ship_name, flag, registered_owner, status, former_names")
    parser.add_argument("--out", type=Path, default=Path("output"))
    args = parser.parse_args()

    results = validate(load_csv(args.master), index_reference(load_csv(args.reference)))
    write_reports(results, args.out)
    print((args.out / "summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
