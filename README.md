# Vessel Data Validator

A Python tool that checks a company's vessel master list against registry data and tells the team which records are correct, which need updating and which need a closer look.

I built the original version during my IT internship at a logistics company. An overseas office needed correct vessel ownership data for its customs work, and the master list held around 5,500 ships. This repository is a clean rewrite of the same logic with invented sample data. It contains no company code or data, and every IMO number in it is made up.

## What it checks

For every vessel in the master list:

1. **IMO number** – it must have 7 digits and a valid check digit. The tool also spots common data-entry mistakes, such as a 9-digit MMSI pasted into the IMO field.
2. **Duplicates** – the same IMO number entered twice.
3. **Registry comparison** – the vessel is looked up by IMO and its name, flag and registered owner are compared using normalised text and a similarity score (`difflib.SequenceMatcher`). Prefixes like `MV` and legal words like `Ltd` are ignored, so `MV AURORA BALTIC` matches `Aurora Baltic`.

Each vessel ends up in exactly one category:

| Category | Meaning | Next step |
|---|---|---|
| `MATCH` | Name, flag and owner agree | Nothing to do |
| `MINOR_DIFFERENCES` | Small spelling or flag difference | Quick check |
| `OWNER_CHANGED` | Registry shows a different owner | Update the master list |
| `RENAMED` | Our name is in the ship's former names | Update the name |
| `SCRAPPED` | Registry says the ship no longer sails | Deactivate the record |
| `NOT_IN_REFERENCE` | Valid IMO, no registry record | Often small or niche carriers; check the carrier's own website |
| `DUPLICATE_IMO` | IMO appears more than once | Merge records |
| `INVALID_IMO` | Missing or wrong IMO | Correct the number |

The summary also lists which carriers have the most vessels missing from the registry, because in the real data those were mostly small regional carriers that needed a different lookup.

## About the reference data

At the company, the registry data came from looking up each IMO number in public maritime registries with a small browser-automation script (Playwright), saving progress after each vessel so the run could be resumed. That part is not included here: those sites have their own terms of use and some require an account. This version reads the registry data from a CSV export instead, so the validation logic can be run and tested by anyone.

## Run it

Requires Python 3.10 or newer. No third-party packages are needed.

```bash
python generate_sample_data.py
python validator.py sample_data/vessel_master_list.csv sample_data/registry_export.csv --out output
```

This writes `output/vessel_report.csv` (one row per vessel, sorted by category) and `output/summary.md`.

## Tests

```bash
pip install pytest
pytest
```

## What I learned

- Validating the input first (the IMO check digit) catches problems that would otherwise look like "not found" results.
- Fuzzy matching needs normalisation before it, or tiny formatting differences hide real matches.
- Putting every record into one clear category made the result something the office could act on, instead of one long list of differences.
