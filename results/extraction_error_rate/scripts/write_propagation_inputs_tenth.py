r"""R221: the tenth amendment's propagation inputs, written into tenth-census/ before the run.

  error-rate-read-stems-tenth.json      the records the tenth census read twice (found in passing), the tail
                                        stratum's 1884/2016 and the eleventh and twelfth amendments' eight records
                                        (entrants/entrants-result.json), beside propagation/error-rate-read-stems.json
  error-rate-confirmed-errors-tenth.json the errors confirmed before repair: repairs/error-rate-confirmed-errors.json,
                                        the tenth census's two (3334/2018, 1206/2014) and the eleventh amendment's two
                                        (3010/2022, 1609/2023), each with its filing figure and opening reserves;
                                        1884/2016 and 2468/2014 have no filing figure, so they give no shift

    python results/extraction_error_rate/scripts/write_propagation_inputs_tenth.py [--dry-run]
"""
import io
import json
import os
import sys

A = r"D:\dev\IME-Lloyds-exposure-composition\results\extraction_error_rate"
DRY = "--dry-run" in sys.argv


def main():
    census = json.load(io.open(os.path.join(A, "tenth-census", "census-tenth-result.json"), encoding="utf-8"))
    passing = {r["stem"]: r for r in census["found_in_passing"]}
    entrants = json.load(io.open(os.path.join(A, "tenth-census", "entrants", "entrants-result.json"),
                                 encoding="utf-8"))
    stems = sorted({"syndicate_" + s for s in passing} | {"syndicate_1884_2016"}
                   | {"syndicate_" + r["stem"] for r in entrants["records"]})
    read = {"purpose": ("the records the tenth amendment's census read twice (the records found in passing, point 4), "
                        "the tail stratum's 1884/2016 and the records the eleventh and twelfth amendments read, read "
                        "beside propagation/error-rate-read-stems.json by error_rate_propagation.py --read-samples"),
            "source": "tenth-census/census-tenth-result.json, tenth-census/entrants/entrants-result.json",
            "n": len(stems), "stems": stems}
    old = json.load(io.open(os.path.join(A, "repairs", "error-rate-confirmed-errors.json"), encoding="utf-8"))
    new = [
        {"stem": "syndicate_3334_2018", "from": "tenth census, found in passing", "adopted_m": -37.982,
         "filing_m": 5.109, "filing_figure_from": "both readings (data/pyd_confirmed_figures.json)",
         "opening_m": 116.773},
        {"stem": "syndicate_1206_2014", "from": "tenth census, found in passing", "adopted_m": 31.6,
         "filing_m": 23.342, "filing_figure_from": "both readings (data/pyd_confirmed_figures.json)",
         "opening_m": 278.997},
        {"stem": "syndicate_3010_2022", "from": "eleventh amendment", "adopted_m": 146.569, "filing_m": -10.926,
         "filing_figure_from": "both readings (data/pyd_confirmed_figures.json; implementation note 9)",
         "opening_m": 118.866},
        {"stem": "syndicate_1609_2023", "from": "eleventh amendment, found in passing", "adopted_m": 11.657,
         "filing_m": 8.834, "filing_figure_from": "both readings (data/pyd_confirmed_figures.json)",
         "opening_m": 88.843},
    ]
    ent = {r["stem"]: r for r in entrants["records"]}
    for n in new:
        key = n["stem"][len("syndicate_"):]
        if key in passing:
            p = passing[key]
            assert p["verdict"] == "error" and p["adopted_m"] == n["adopted_m"] and p["filing_figure_m"] == n["filing_m"], p
        else:
            e = ent[key]
            assert e["outcome"] == "repaired" and e["adopted_m"] == n["adopted_m"] and e["figure_m"] == n["filing_m"], e
    if {e["stem"] for e in old} & {n["stem"] for n in new}:
        raise SystemExit("already listed")
    errs = old + new
    if DRY:
        print("ready: %d read, %d confirmed errors" % (len(stems), len(errs)))
        return 0
    for name, obj in (("error-rate-read-stems-tenth.json", read), ("error-rate-confirmed-errors-tenth.json", errs)):
        with io.open(os.path.join(A, "tenth-census", name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")
    print("written: %d read (%s), %d confirmed errors" % (len(stems), stems, len(errs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
