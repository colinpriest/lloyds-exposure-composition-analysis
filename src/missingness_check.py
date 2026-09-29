"""Audit model-sample selection using the inferential disposition of every filing.

The extraction repository contains stubs for reasons that must not be mixed:
some reports are substantively too new to have an eligible mature cohort, some have
an eligible outcome that the extraction did not recover, and some have no deterministic
reading: the extraction's parsers found no prior-year figure and its models were not run.
The last condition says what the extraction did, and nothing about the filing (which may
still print a table the parsers could not read), so it is not evidence that the economic
outcome does not exist. This audit combines the loader's record-level disposition ledger with its
parsed observations and classifies all 1,065 filings before calculating any
selection diagnostic.

The inferential population is a gross-basis prior-year development ratio with a
positive opening-reserve base, for a syndicate writing business in the year: a run-off
year writes no premium, has no premium-mix composition, and is a scientific exclusion,
as the loader removes it before the corpus. The response for selection diagnostics is membership
in the current model sample, not availability of one extracted field. The primary
estimand is deliberately limited to the supported, disclosure-defined population.
Eligibility-unresolved filings are reported separately and carried into a dedicated
sensitivity; they are not silently treated as either eligible or ineligible.

It also writes two reconciliations the manuscript quotes as counts (review of 29 September 2026, M-8):
`basis_exclusions_reconciliation`, which ties the loader flow's 125 basis exclusions to this
partition's 133 (the other 8 net- or unstated-basis records leave the flow earlier, at the
unusable-severity step, whose 15 it itemises), and `assumed_business_regime`, the composition of the
regime rows in each of the three populations they are quoted in (scanned filings, corpus, working
sample). Each count is computed from the ledgers and registers and its arithmetic asserted.

Run: python src/missingness_check.py
"""
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

import assumed_business


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
            # the extraction's own status and words (round 62's verification, MAT-2): its parsers found no
            # prior-year figure and its models were not run, which establishes nothing about the filing
            if source.get("status") != "no_deterministic_reading":
                raise AssertionError(f"an EXCLUDED record whose status is not no_deterministic_reading "
                                     f"({source.get('status')!r}): classify it: {entry['file']}")
            category, detail = "eligibility_unresolved", "no_deterministic_reading"
            economic, disclosure, extraction = (
                "unresolved", "not_established_the_filing_was_not_read", "parsers_found_no_figure_models_not_run"
            )
            evidence = source.get(
                "exclusion_reason",
                "no deterministic reading: the parsers found no prior-year figure and the models were not run; "
                "nothing is established about the filing",
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
        elif disposition == "IN RUNOFF":
            # A run-off year writes no premium, so it has no premium-mix composition. The loader removes it before
            # the corpus by design, as it removes a year without a positive reserve base (the data-audit appendix:
            # "pure run-off years ... are excluded"). Round 62 met the first one, 2468/2022, and this classifier,
            # which had no branch for it, stopped the regeneration pass.
            category, detail = "scientific_exclusion", "in_runoff_no_written_premium"
            economic, disclosure, extraction = (
                "outside_written-premium_estimand", "development_record_present", "parsed"
            )
            evidence = "run-off year: no gross premium written, so no premium-mix composition"
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


def basis_exclusions_reconciliation(rows, ledger, flow):
    """The loader flow's basis step against this partition's basis exclusions, and the unusable-severity
    step's members, from the two ledgers; the arithmetic between them is asserted."""
    disp = {e["file"]: e["disposition"] for e in ledger}
    basis_rows = [r for r in rows if r["detail"] == "non_gross_or_unstated_development"]
    at_basis_step = [r for r in basis_rows if disp[r["file"]] in ("CORPUS:NET_BASIS", "CORPUS:UNKNOWN_BASIS")]
    at_severity_step = [r for r in basis_rows if disp[r["file"]] == "CORPUS:INCOMPLETE"]
    other = [r for r in basis_rows if r not in at_basis_step and r not in at_severity_step]
    n_net = sum(1 for r in at_basis_step if disp[r["file"]] == "CORPUS:NET_BASIS")
    tows = flow["to_working_sample"]
    if other or len(at_basis_step) != tows["net_or_unstated_basis"]:
        raise AssertionError("basis exclusions: the flow's basis step (%d) is not this partition's basis "
                             "records at that step (%d; %d elsewhere)"
                             % (tows["net_or_unstated_basis"], len(at_basis_step), len(other)))
    severity = [r for r in rows
                if (disp[r["file"]] == "CORPUS:INCOMPLETE" and r["detail"] != "missing_lob_composition")
                or disp[r["file"]] == "CORPUS:PROVISION_MOVEMENT_NOT_DEVELOPMENT"]
    components = dict(sorted(Counter(r["detail"] for r in severity).items()))
    if len(severity) != tows["unusable_severity"]:
        raise AssertionError("basis exclusions: %d records at the unusable-severity step against the flow's %d"
                             % (len(severity), tows["unusable_severity"]))
    return {
        "note": ("the loader flow removes records in order, so a net- or unstated-basis record whose severity "
                 "is also unusable leaves at the unusable-severity step; this partition classifies every "
                 "filing by its basis first"),
        "flow_basis_step": len(at_basis_step),
        "flow_basis_step_net": n_net,
        "flow_basis_step_unstated": len(at_basis_step) - n_net,
        "basis_records_at_unusable_severity_step": len(at_severity_step),
        "basis_records_at_unusable_severity_step_files": sorted(r["file"] for r in at_severity_step),
        "inferential_basis_exclusions": len(basis_rows),
        "identity_basis": "%d + %d = %d" % (len(at_basis_step), len(at_severity_step), len(basis_rows)),
        "flow_unusable_severity_step": len(severity),
        "unusable_severity_components": components,
        "identity_unusable_severity": "%s = %d" % (" + ".join(str(v) for v in components.values()),
                                                     len(severity)),
    }


def regime_composition(rows):
    """The assumed-business regime (assumed_business.sources) in each population it is quoted in: every
    scanned filing, the corpus, the working sample; each row counted once, by its first source among a
    RITC flag, a confirmed inward transfer and a confirmed take-on."""
    src = assumed_business.sources()
    with io.open(assumed_business.RITC_SCAN, encoding="utf-8") as fh:
        scanned = {k for k, v in json.load(fh).items() if isinstance(v, dict)}
    corpus = {"%d_%d" % (r["syndicate"], r["year"]) for r in rows if r["observation"] is not None}
    sample = {"%d_%d" % (r["syndicate"], r["year"]) for r in rows if r["category"] == "working_sample"}

    def kind(k):
        s = src[k]
        if any(x.startswith("ritc_") for x in s):
            return "ritc_flagged"
        if any(x in ("transfer_inward", "transfer_both") for x in s):
            return "confirmed_transfer_not_flagged"
        return "takeon_only"

    def population(keys):
        regime = sorted(set(src) & keys)
        comp = Counter(kind(k) for k in regime)
        transfers = [k for k in regime if any(x in ("transfer_inward", "transfer_both") for x in src[k])]
        return {"n_rows": len(keys), "n_regime": len(regime),
                "composition": {c: comp.get(c, 0) for c in ("ritc_flagged", "confirmed_transfer_not_flagged",
                                                            "takeon_only")},
                "confirmed_transfers": len(transfers),
                "confirmed_transfers_also_flagged": sum(1 for k in transfers
                                                        if any(x.startswith("ritc_") for x in src[k])),
                "takeons": sum(1 for k in regime if "transfer_takeon" in src[k])}

    out = {"note": ("composition counts each regime row once: RITC-flagged first, then a confirmed inward "
                    "transfer the scan did not flag, then a confirmed take-on in neither"),
           "scanned_filings": population(scanned), "corpus": population(corpus),
           "working_sample": population(sample)}
    missing = sorted(set(src) - scanned)
    if missing:
        raise AssertionError("regime rows outside the scanned filings: %s" % missing)
    for name in ("scanned_filings", "corpus", "working_sample"):
        p = out[name]
        if sum(p["composition"].values()) != p["n_regime"]:
            raise AssertionError("regime composition does not add up in the %s" % name)
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
            "selection_response": f"membership in the {len(included)}-record model sample",
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
        "basis_exclusions_reconciliation": basis_exclusions_reconciliation(
            rows, list(csv.DictReader(io.open(SD / "results" / "disposition_ledger.csv", encoding="utf-8"))),
            json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))["disposition_flow"]),
        "assumed_business_regime": regime_composition(rows),
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
