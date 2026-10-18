"""Create a fake vessel master list and a fake registry export.

Every name, owner and IMO number here is invented. IMO numbers are generated
with a valid check digit so they look realistic, but they do not refer to
real ships.
"""

import csv
import random
from pathlib import Path

WORDS = ["Aurora", "Baltic", "Cedar", "Dolphin", "Eagle", "Falcon", "Glory", "Horizon", "Ivy", "Juniper",
         "Kestrel", "Lotus", "Meridian", "Nordic", "Orion", "Pioneer", "Quest", "Raven", "Sierra", "Tango"]
FLAGS = ["PA", "LR", "MH", "MT", "SG", "DE", "GR", "CY", "BS", "HK"]
OWNERS = ["Bluewater Holdings Ltd", "Seaways Capital SA", "Northern Star Shipping Inc", "Harbourline Maritime GmbH",
          "Coral Bay Leasing Ltd", "Ocean Ridge Pte Ltd", "Tidewater Assets AS", "Meridian Fleet Co"]
CARRIERS = ["Global Container Line", "Atlantic Feeder Co", "Island Hopper Lines", "Pacific Express", "Small Coastal Shipping"]


def make_imo(rng: random.Random) -> str:
    first_six = [rng.randint(0, 9) for _ in range(6)]
    first_six[0] = rng.choice([8, 9])
    check = sum(d * (7 - i) for i, d in enumerate(first_six)) % 10
    return "".join(map(str, first_six)) + str(check)


def generate(count: int = 800, seed: int = 11):
    rng = random.Random(seed)
    master, reference = [], []
    used = set()

    for _ in range(count):
        imo = make_imo(rng)
        while imo in used:
            imo = make_imo(rng)
        used.add(imo)
        name = f"{rng.choice(WORDS)} {rng.choice(WORDS)}"
        flag, owner, carrier = rng.choice(FLAGS), rng.choice(OWNERS), rng.choice(CARRIERS)
        master.append({"imo": imo, "vessel_name": name, "flag": flag, "owner": owner, "carrier": carrier})

        if carrier == "Small Coastal Shipping" and rng.random() < 0.7:
            continue  # small carriers are often missing from the registry
        ref = {"imo": imo, "ship_name": name, "flag": flag, "registered_owner": owner,
               "status": "IN SERVICE", "former_names": ""}
        roll = rng.random()
        if roll < 0.05:
            ref["status"] = "BROKEN UP"
        elif roll < 0.10:
            ref["ship_name"] = f"{rng.choice(WORDS)} {rng.choice(WORDS)}"
            ref["former_names"] = name
        elif roll < 0.18:
            ref["registered_owner"] = rng.choice([o for o in OWNERS if o != owner])
        elif roll < 0.26:
            ref["ship_name"] = "MV " + name.upper()
            ref["registered_owner"] = owner.replace("Ltd", "Limited")
        elif roll < 0.30:
            ref["flag"] = rng.choice([f for f in FLAGS if f != flag])
        reference.append(ref)

    # A few typical data-entry problems in the master list.
    master[0]["imo"] = master[0]["imo"][:6]                        # digit missing
    master[1]["imo"] = master[1]["imo"][:6] + str((int(master[1]["imo"][6]) + 1) % 10)  # typo
    master[2]["imo"] = "2" + master[2]["imo"] + "0"               # MMSI pasted instead
    master.append(dict(master[10], vessel_name=master[10]["vessel_name"] + " II"))  # duplicate IMO
    rng.shuffle(master)
    return master, reference


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    master, reference = generate()
    write(Path("sample_data/vessel_master_list.csv"), master)
    write(Path("sample_data/registry_export.csv"), reference)
    print(f"wrote {len(master)} vessels and {len(reference)} registry records to sample_data/")
