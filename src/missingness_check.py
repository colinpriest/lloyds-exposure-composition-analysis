"""Audit model-sample selection using the inferential disposition of every filing.

The extraction repository contains stubs for reasons that must not be mixed:
some reports are substantively too new to have an eligible mature cohort, some have
an eligible outcome that the extraction did not recover, and some merely contain no
development disclosure the extraction could use. The last condition is evidence
about disclosure and extraction, not evidence that the economic outcome does not
exist. This audit combines the loader's record-level disposition ledger with its
parsed observations and classifies all 1,065 filings before calculating any
selection diagnostic.

The inferential population is a gross-basis prior-year development ratio with a
positive opening-reserve base. The response for selection diagnostics is membership
in the current model sample, not availability of one extracted field. The primary
estimand is deliberately limited to the supported, disclosure-defined population.
Eligibility-unresolved filings are reported separately and carried into a dedicated
sensitivity; they are not silently treated as either eligible or ineligible.

Run: python src/missingness_check.py
"""
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats


SD = Path(__file__).resolve().parent.parent
STRUCTURAL_AUDIT = SD / "pdf_extraction" / "audit" / "structural_eligibility_audit.json"


def _structural_decisions():
    """The filing-page decisions; extraction skip flags are never eligibility evidence."""
    with io.open(STRUCTURAL_AUDIT, encoding="utf-8") as handle:
        audit = json.load(handle)
    records = {record["file"]: record for record in audit["records"]}
    if len(records) != audit["counts"]["reviewed"]:
        raise ValueError("structural eligibility audit is not one decision per reviewed filing")
    return records


def _key_from_file(name):
    base = Path(name).stem.removeprefix("syndicate_")
    syndicate, year = base.rsplit("_", 1)
    return int(syndicate), int(year)


def _model_reserve(name, currencies, rates):
    """First positive model reserve, in GBP, for a pre-corpus record."""
    with io.open(SD / "pdf_extraction" / name, encoding="utf-8") as fh:
        record = json.load(fh)
    value = next(
        (float(model["opening_reserves_gbp_m"])
         for model in (record.get("models") or {}).values()
         if isinstance(model.get("opening_reserves_gbp_m"), (int, float))
         and model["opening_reserves_gbp_m"] > 0),
        None,
    )
    syndicate, year = _key_from_file(name)
    if value is not None and currencies.get(f"{syndicate}_{year}") == "USD":
        value /= rates[year]
    return value


def _source_record(name):
    with io.open(SD / "pdf_extraction" / name, encoding="utf-8") as fh:
        return json.load(fh)


def classify_filings():
    """Return mutually exclusive inferential dispositions for all retrieved files."""
    with io.open(SD / "results" / "disposition_ledger.csv", encoding="utf-8") as fh:
        ledger = list(csv.DictReader(fh))
    with io.open(SD / "model" / "exposure_results.json", encoding="utf-8") as fh:
        exposure = json.load(fh)

    observations = {
        (int(row["syndicate"]), int(row["year"])): row
        for row in exposure["observations"]
    }
    structural = _structural_decisions()
    rows = []
    for entry in ledger:
        key = _key_from_file(entry["file"])
        disposition = entry["disposition"]
        obs = observations.get(key)
        source = _source_record(entry["file"])

        if disposition == "SKIPPED":
            reviewed = structural.get(entry["file"])
            if reviewed is None:
                raise AssertionError(
                    f"SKIPPED filing lacks an independent source-page eligibility decision: {entry['file']}")
            if reviewed["economic_eligibility"] == "ineligible":
                category, detail = "structural_no_eligible_outcome", "no_mature_cohort"
                economic, disclosure, extraction = (
                    "ineligible", "not_applicable", "source_page_audit_after_pre_model_skip"
                )
                evidence = reviewed["mature_cohort_calculation"]
            elif reviewed["economic_eligibility"] == "unresolved":
                category, detail = "eligibility_unresolved", "source_page_audit_unresolved"
                economic, disclosure, extraction = (
                    "unresolved", "reviewed_but_indeterminate", "pre_model_skip"
                )
                evidence = reviewed["review_note"] or reviewed["mature_cohort_calculation"]
            else:
                raise AssertionError(
                    f"eligible audited filing is still SKIPPED; regenerate loader output: {entry['file']}")
        elif disposition == "EXCLUDED":
            category, detail = "eligibility_unresolved", "no_development_disclosure_found"
            economic, disclosure, extraction = (
                "unresolved", "no_triangle_or_reserve_text_found", "no_usable_development_evidence"
            )
            evidence = source.get(
                "exclusion_reason",
                "no triangle or reserve-movement text found; economic eligibility not determined",
            )
        elif disposition == "NO_RESERVES":
            category, detail = "scientific_exclusion", "no_positive_reserve_base"
            economic, disclosure, extraction = (
                "outside_positive-reserve_estimand", "development_record_present", "parsed"
            )
            evidence = "no positive opening-reserve base"
        elif disposition == "INCOMPLETE_PRE":
            category, detail = "eligible_outcome_unavailable", "no_usable_development_reading"
            economic, disclosure, extraction = (
                "eligible", "development_field_sought", "dual_model_reading_unavailable"
            )
            evidence = entry.get("reason") or "no model supplied a usable development reading"
        elif obs is None:
            raise AssertionError(f"unclassified pre-corpus disposition: {entry}")
        elif (obs.get("data_quality_tag") in ("NET_BASIS", "UNKNOWN_BASIS")
              or obs.get("pyd_basis") in ("net", "unknown")):
            category, detail = "scientific_exclusion", "non_gross_or_unstated_development"
            economic, disclosure, extraction = "eligible", "development_observed", "parsed"
            evidence = "development basis is net or unstated"
        elif obs.get("data_quality_tag") == "TAKEON_NOT_DEVELOPMENT":
            category, detail = "scientific_exclusion", "takeon_not_development"
            economic, disclosure, extraction = (
                "outside_development_estimand", "movement_observed", "parsed"
            )
            evidence = "adjudicated as take-on rather than prior-year development"
        elif obs.get("data_quality_tag") == "PROVISION_MOVEMENT_NOT_DEVELOPMENT":
            category, detail = "scientific_exclusion", "provision_movement_not_development"
            economic, disclosure, extraction = (
                "outside_development_estimand", "movement_observed", "parsed"
            )
            evidence = "adjudicated as provision movement rather than prior-year development"
        elif obs.get("pyd_pct") is None:
            category, detail = "eligible_outcome_unavailable", "gross_development_unavailable"
            economic, disclosure, extraction = (
                "eligible", "development_disclosure_present", "unusable_outcome"
            )
            evidence = "gross development outcome unavailable after parsing"
        elif not obs.get("opening_reserves_gbp_m"):
            category, detail = "scientific_exclusion", "no_positive_reserve_base"
            economic, disclosure, extraction = (
                "outside_positive-reserve_estimand", "development_observed", "parsed"
            )
            evidence = "no positive opening-reserve base"
        elif obs.get("hhi") is None:
            category, detail = (
                "eligible_observed_composition_unavailable", "missing_lob_composition"
            )
            economic, disclosure, extraction = (
                "eligible", "development_observed", "composition_unavailable"
            )
            evidence = "eligible gross development observed; composition unavailable"
        else:
            category, detail = "working_sample", "observed_eligible_complete"
            economic, disclosure, extraction = "eligible", "development_observed", "complete"
            evidence = "eligible gross development, positive reserve and composition observed"

        rows.append({
            "file": entry["file"],
            "syndicate": key[0],
            "year": key[1],
            "category": category,
            "detail": detail,
            "economic_eligibility": economic,
            "disclosure_availability": disclosure,
            "extraction_status": extraction,
            "classification_evidence": evidence,
            "observation": obs,
        })

    if len(rows) != len(ledger) or len({r["file"] for r in rows}) != len(rows):
        raise AssertionError("the disposition table is not one row per filing")
    return rows


def add_size_proxies(rows):
    """Attach observed or same-syndicate opening-reserve size to target rows."""
    with io.open(SD / "pdf_extraction" / "currency_scan.json", encoding="utf-8") as fh:
        currencies = {k: v["currency"] for k, v in json.load(fh)["reports"].items()}
    with io.open(SD / "model" / "fx_rates_h10.json", encoding="utf-8") as fh:
        rates = {int(y): v["usd_per_gbp"]
                 for y, v in json.load(fh)["year_end_rates"].items()}

    by_syndicate = defaultdict(list)
    direct = {}
    for row in rows:
        obs = row["observation"]
        value = (float(obs["opening_reserves_gbp_m"])
                 if obs and obs.get("opening_reserves_gbp_m") else None)
        if value is None:
            value = _model_reserve(row["file"], currencies, rates)
        direct[row["file"]] = value
        if value is not None:
            by_syndicate[row["syndicate"]].append(value)
    medians = {s: float(np.median(values)) for s, values in by_syndicate.items()}
    for row in rows:
        row["size_proxy"] = direct[row["file"]]
        row["size_proxy_source"] = (
            "filing" if row["size_proxy"] is not None else "unavailable"
        )
        if row["size_proxy"] is None and row["syndicate"] in medians:
            row["size_proxy"] = medians[row["syndicate"]]
            row["size_proxy_source"] = "same_syndicate_median"
    return rows


def _ols_indicator(sample, flagged_syndicates):
    S = np.array([r["observation"]["s_raw_a"] for r in sample], float)
    R = np.array([r["observation"]["opening_reserves_gbp_m"] for r in sample], float)
    flag = np.array([r["syndicate"] in flagged_syndicates for r in sample], float)
    X = np.column_stack([np.ones(len(S)), np.log(R / 500.0), flag])
    out = {}
    for y, prefix in ((S, "signed_S"), (np.abs(S), "abs_S")):
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        variance = (resid @ resid) / (len(y) - X.shape[1])
        se = np.sqrt(np.diag(variance * np.linalg.inv(X.T @ X)))
        z = beta[2] / se[2]
        out[f"{prefix}_unavailable_history_coef"] = float(beta[2])
        out[f"{prefix}_p"] = float(2 * (1 - stats.norm.cdf(abs(z))))
    out["n"] = len(sample)
    return out


def main():
    rows = add_size_proxies(classify_filings())
    counts = Counter(row["category"] for row in rows)
    details = Counter(row["detail"] for row in rows)
    target = [r for r in rows if r["category"] in {
        "eligible_outcome_unavailable",
        "eligible_observed_composition_unavailable",
        "working_sample",
    }]
    unresolved = [r for r in rows if r["category"] == "eligibility_unresolved"]
    missing_size = [r["file"] for r in target if r["size_proxy"] is None]
    if missing_size:
        raise AssertionError(f"target records lack a size proxy: {missing_size}")

    included = [r for r in target if r["category"] == "working_sample"]
    not_included = [r for r in target if r["category"] != "working_sample"]
    u = stats.mannwhitneyu(
        [r["size_proxy"] for r in included],
        [r["size_proxy"] for r in not_included],
        alternative="two-sided",
    )
    by_year = {}
    for year in sorted({r["year"] for r in target}):
        year_rows = [r for r in target if r["year"] == year]
        n_in = sum(r["category"] == "working_sample" for r in year_rows)
        by_year[str(year)] = {"model_sample": n_in, "target_population": len(year_rows)}

    unavailable = [r for r in target if r["category"] == "eligible_outcome_unavailable"]
    flagged_syndicates = {r["syndicate"] for r in unavailable}
    outcome_diag = _ols_indicator(included, flagged_syndicates)

    result = {
        "definition": {
            "supported_disclosure_defined_target": (
                "gross prior-year development on an eligible mature cohort with a positive "
                "opening-reserve base, among filings for which the ledger supports economic "
                "eligibility; no-development-disclosure filings are outside this primary "
                "target because their eligibility is unresolved"
            ),
            "broader_potential_target": (
                "the supported target plus every eligibility-unresolved filing, under the "
                "sensitivity assumption that all such filings were economically eligible"
            ),
            "selection_response": "membership in the 685-record model sample",
            "size_proxy": "filing reserve where available; otherwise same-syndicate median",
        },
        "n_filings": len(rows),
        "disposition_counts": dict(sorted(counts.items())),
        "disposition_detail_counts": dict(sorted(details.items())),
        "n_supported_target_population": len(target),
        "n_target_population": len(target),
        "n_eligibility_unresolved": len(unresolved),
        "n_broader_potential_target_if_all_unresolved_eligible": len(target) + len(unresolved),
        "n_model_sample": len(included),
        "n_eligible_outcome_unavailable": len(unavailable),
        "n_distinct_syndicates_with_unavailable_outcome": len(flagged_syndicates),
        "n_syndicates_with_unavailable_outcome_and_no_model_record": len(
            flagged_syndicates - {r["syndicate"] for r in included}
        ),
        "model_sample_selection_by_size": {
            "median_size_included": float(np.median([r["size_proxy"] for r in included])),
            "median_size_not_included": float(np.median([r["size_proxy"] for r in not_included])),
            "n_included": len(included),
            "n_not_included": len(not_included),
            "mann_whitney_p": float(u.pvalue),
        },
        "model_sample_by_year": by_year,
        "outcome_given_size": outcome_diag,
        "eligible_unavailable_records": [r["file"] for r in unavailable],
        "eligibility_unresolved_audit": {
            "classification_rule": (
                "The extraction found neither a claims-development triangle nor reserve-"
                "movement text. This establishes disclosure/extraction unavailability, not "
                "economic ineligibility. Eligibility therefore remains unresolved."
            ),
            "n_records": len(unresolved),
            "n_with_size_proxy": sum(r["size_proxy"] is not None for r in unresolved),
            "n_without_size_proxy": sum(r["size_proxy"] is None for r in unresolved),
            "records": [
                {
                    "file": r["file"],
                    "syndicate": r["syndicate"],
                    "year": r["year"],
                    "economic_eligibility": r["economic_eligibility"],
                    "disclosure_availability": r["disclosure_availability"],
                    "extraction_status": r["extraction_status"],
                    "evidence": r["classification_evidence"],
                    "size_proxy_gbp_m": r["size_proxy"],
                    "size_proxy_source": r["size_proxy_source"],
                }
                for r in unresolved
            ],
        },
        "withdrawn_diagnostic": (
            "The former 131 missing-opening-reserve records and 33 orphan failures mixed "
            "structural stubs with exclusions and are not an inferential missingness "
            "population. No-development-disclosure records are not called structural."
        ),
    }
    out = SD / "results" / "missingness_check_results.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    ledger_out = SD / "results" / "inferential_disposition_ledger.csv"
    with ledger_out.open("w", encoding="utf-8", newline="") as fh:
        fields = [
            "file", "syndicate", "year", "category", "detail",
            "economic_eligibility", "disclosure_availability", "extraction_status",
            "classification_evidence", "in_supported_target_population",
            "in_broader_potential_target", "in_model_sample",
            "eligible_outcome_observed", "size_proxy_gbp_m", "size_proxy_source",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "file": row["file"],
                "syndicate": row["syndicate"],
                "year": row["year"],
                "category": row["category"],
                "detail": row["detail"],
                "economic_eligibility": row["economic_eligibility"],
                "disclosure_availability": row["disclosure_availability"],
                "extraction_status": row["extraction_status"],
                "classification_evidence": row["classification_evidence"],
                "in_supported_target_population": row in target,
                "in_broader_potential_target": row in target or row in unresolved,
                "in_model_sample": row["category"] == "working_sample",
                "eligible_outcome_observed": row["category"] in {
                    "eligible_observed_composition_unavailable", "working_sample",
                },
                "size_proxy_gbp_m": (
                    "" if row["size_proxy"] is None else f'{row["size_proxy"]:.12g}'
                ),
                "size_proxy_source": row["size_proxy_source"],
            })

    print("Inferential disposition:")
    for name, n in sorted(counts.items()):
        print(f"  {name:43s} {n:4d}")
    print(f"Supported target population: {len(target)}; model sample: {len(included)}")
    print(f"Eligibility unresolved: {len(unresolved)}")
    print(f"Eligible outcomes unavailable: {len(unavailable)}")
    print(f"Wrote {out}")
    print(f"Wrote {ledger_out}")


if __name__ == "__main__":
    main()
