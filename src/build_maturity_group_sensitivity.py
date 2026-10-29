"""Build the recovered-groups-omitted maturity input without altering the primary.

Existing older groups remain. In 1225 the grouped source total replaces a
single-year value; the explicitly recorded values below restore that year only.
Usage: python src/build_maturity_group_sensitivity.py --output PATH
"""
import argparse
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDIVIDUAL_1225 = {
    "1225_2016": (2011, 240.3), "1225_2017": (2012, 173.6),
    "1225_2018": (2013, 234.2), "1225_2019": (2014, 210.1),
    "1225_2020": (2015, 186.1), "1225_2021": (2016, 278.4),
    "1225_2022": (2017, 372.1),
}


def build(source, overrides):
    out = copy.deepcopy(source)
    changed = []
    for ident, entry in overrides.items():
        if "additional_grouped_cohort" not in entry and ident not in INDIVIDUAL_1225:
            continue
        year = int(ident.split("_")[1])
        values = {int(u): v for u, v in entry["current_estimate_by_underwriting_year"].items()}
        if ident in INDIVIDUAL_1225:
            cohort, value = INDIVIDUAL_1225[ident]
            if cohort not in values:
                raise ValueError("missing 1225 grouped cohort: " + ident)
            values[cohort] = value
        opening = [(u, year - 1 - u, v) for u, v in values.items() if u <= year - 1]
        mature = [row for row in opening if row[0] <= year - 2]
        rec = out["records"][ident]
        rec["n_uw_years"] = len(values)
        rec["opening_uw_years"] = [u for u, _, _ in opening]
        rec["mature_uw_years"] = [u for u, _, _ in mature]
        for delta in (None, 4., 2., 1.):
            tag = "phi_delta_inf" if delta is None else "phi_delta_%g" % delta
            def weight(age):
                return 1.0 if delta is None else math.exp(-age / delta)
            rec[tag] = (sum(abs(v) * weight(age) for _, age, v in mature) /
                        sum(abs(v) * weight(age) for _, age, v in opening))
        rec["source_override"]["sensitivity_note"] = (
            "Recovered source group removed, or replaced with the previously selected individual-year "
            "value for 1225 records. Other previously captured groups remain.")
        changed.append(ident)
    return out, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite: %s" % args.output)
    source = json.loads((ROOT / "model/maturity_share.json").read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / "data/maturity_proxy_source_overrides.json").read_text(encoding="utf-8"))["records"]
    result, changed = build(source, overrides)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Wrote %s; changed %d records" % (args.output, len(changed)))


if __name__ == "__main__":
    main()
