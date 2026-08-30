# Vignette Specifications

> **Status: superseded.**
> This document describes the earlier sequential / least-squares line-of-business
> projection, which was replaced by the robust Bayesian pooling operator
> (size and concentration, Student-t, two-regime RITC tail). It is retained as a record
> of that stage and is **not** a description of the current method. See
> `scaling_analysis_writeup.md` and the manuscript.


In addition to the paper pack, we need automatically generated vignette materials, written to the existing vignettes subfolder of the project. All the vignette tables should be output in both xslx format and LaTeX format. All of the vignette figures should be output in png format

Vignette 1 output should go into the vignettes/vignette-1 folder.

Vignette 2 output should go into the vignettes/vignette-2 folder.

## What each vignette must produce

### Common rule for both vignettes

All distributional outputs should be based on the **signed PYD ratio** (S_i), because that is the paper’s adverse-tail capital object. Absolute severity belongs in the regression / dispersion part, not in the worked capital vignettes.

For both vignettes, use the same three-stage notation everywhere:

- `S_raw`: raw donor signed PYD ratio
- `S_mix`: LoB-mix-standardised ratio
- `S_adj`: fully adjusted ratio after reserve-size scaling

That is already how the appendix worked example is structured.

---

## Vignette 1: new £500m target syndicate with too little internal history

Your proposed outputs are basically right. I would define the required paper-pack outputs as:

### 1) Target profile card

A one-row table or JSON block containing:

- vignette ID
- target label
- target reserve size
- exact LoB weights
- target HHI
- sample subset used for donor pool
- donor count
- adverse donor count
- tail support count at 99%
- tail support count at 99.5%

The last four are important because the current paper already reports tail-support counts and bootstrap uncertainty for capital analysis, so the vignette pack should carry that over.

### 2) Two exact worked donor transformations

For each donor, generate:

- donor syndicate-year ID
- donor reserve size
- donor LoB weights
- donor HHI
- raw PYD amount
- raw signed ratio `S_raw`
- full line-level table used in the mix projection:
  - LoB
  - source weight (w^{(s)}_{i\ell})
  - target weight (w^{(q)}_\ell)
  - line-level ratio (s_{i\ell})
  - contribution (w^{(q)}*\ell s*{i\ell})
- `S_mix`
- size function inputs:
  - (R_i)
  - (R_q)
  - (V_{size}(R_i))
  - (V_{size}(R_q))
  - (\lambda_i^{(q)})
- `S_adj`
- percentage change raw→mix
- percentage change mix→adj
- percentage change raw→adj

### 3) Automatic donor-selection rules

You need these, otherwise Python will pick arbitrary examples.

Use two distinct rules:

**Example A: size-mismatch donor**

- complete line-level reconstruction required
- same sign as the target application you want to illustrate, preferably adverse
- choose donor maximising `abs(log(R_i / R_q))`
- subject to concentration being reasonably similar, e.g. `abs(HHI_i - HHI_q) <= 0.05`
- fallback: if none, use the smallest `abs(HHI_i - HHI_q)` among the top 10 size mismatches

**Example B: concentration-mismatch donor**

- complete line-level reconstruction required
- same sign preference
- choose donor maximising concentration mismatch, preferably Hellinger distance in weights
- subject to size being reasonably similar, e.g. `0.67 <= R_i / R_q <= 1.5`
- fallback: use smallest `abs(log(R_i / R_q))` among top 10 mix mismatches

That gives you one example that isolates size and one that isolates mix.

### 4) Main distribution figure

Your histogram/KDE comparison is good, but define it precisely:

- plot object: signed PYD ratio
- series:
  - raw market donor distribution
  - fully adjusted target-basis distribution
- same x-axis limits for both
- vertical lines for:
  - mean
  - 75th percentile
  - VaR99
  - VaR99.5
- show donor count and adverse count in subtitle
- use one consistent bandwidth rule for KDE, stored in metadata

### 5) Tail figure

This is the biggest thing you are still missing.

A histogram/KDE is not enough for a paper about tail distortion. Add a **tail-focused empirical CDF / survivor / exceedance plot** on the adverse side.

Required output:

- x-axis: signed PYD ratio on adverse side only
- y-axis: exceedance probability or empirical survivor function
- raw vs adjusted overlaid
- mark 99% and 99.5% points

This will make the worked vignette visibly relevant to the 1-in-200 question.

### 6) Distribution-statistics table

Your list is almost right, but add a few columns.

Required columns:

- distribution label
- n
- adverse n
- mean
- standard deviation
- Q75
- VaR99
- VaR99.5
- raw→adjusted delta for each quantile
- raw→adjusted percentage delta for each quantile

I would label `Q75` rather than `75% VaR`, unless you want strict internal consistency with your code, because referees may find “VaR75” odd.

### 7) Bootstrap and support table

This is also required, not optional.

For each of VaR99 and VaR99.5, report:

- point estimate
- 95% bootstrap CI lower
- 95% bootstrap CI upper
- tail support count

That is already the logic of Tables 6 and 7 in the paper, so the vignette pack should mirror it.

### 8) Decomposition summary

A one-row table:

- Raw
- Mix-adjusted
- Fully adjusted
- Mix effect
- Size effect

This keeps the worked vignette visually aligned with Table 5.

---

## Vignette 2: syndicate that exits one LoB and becomes smaller and more concentrated

This one needs one extra layer: **old profile vs new profile**.

### 1) Target transition card

Required fields:

- old profile label
- new profile label
- old reserve size
- new reserve size
- old exact LoB weights
- new exact LoB weights
- old HHI
- new HHI
- dropped LoB
- dropped LoB weight
- size change (%)
- HHI change
- narrative reason label, e.g. “exit of Marine after weak profitability”

This should be the first object for vignette 2.

### 2) Two exact worked donor transformations to the new profile

Same structure as vignette 1, but the target is the **new** profile.

Use the same automatic donor-selection rules, but relative to the new profile.

### 3) Before/after target-basis transformation table

This is essential for vignette 2 and currently missing from your list.

For every donor in the common donor pool, compute:

- `S_raw`
- `S_mix_old`
- `S_adj_old`
- `S_mix_new`
- `S_adj_new`

Then generate a summary table with:

- mean(`S_adj_old`)
- mean(`S_adj_new`)
- sd(`S_adj_old`)
- sd(`S_adj_new`)
- Q75 old/new
- VaR99 old/new
- VaR99.5 old/new
- absolute delta old→new
- percentage delta old→new

This is the core output that proves the old internal profile is no longer representative.

### 4) Main comparison figure

Your proposed figure is right:

- raw market distribution
- distortion-adjusted distribution for old profile
- distortion-adjusted distribution for new profile

Same x-axis, same bandwidth, same vertical quantile markers.

### 5) Tail comparison figure

Again, required:

- empirical survivor / exceedance plot
- raw vs adjusted-old vs adjusted-new
- mark 99% and 99.5%

This is the figure that will visually show how ceasing to write the LoB changes the adverse tail.

### 6) Distribution-statistics table

Required columns:

- distribution label
- n
- adverse n
- mean
- standard deviation
- Q75
- VaR99
- VaR99.5

Required rows:

- raw market
- adjusted old profile
- adjusted new profile
- delta old→new

### 7) Old→new change decomposition

This is the second major thing you are missing.

Because vignette 2 is about a **profile change**, you should decompose the change from `adjusted old` to `adjusted new` into:

- mix-change effect
- size-change effect

Do this with the same logic as the main paper:

- old profile
- old mix + new size
- new mix + old size
- new profile
- Shapley or sequential decomposition

Without this, the reader sees that the distribution changed, but not how much came from dropping the LoB versus becoming smaller.

### 8) A very useful “profile transition” figure

A small waterfall or arrow chart:

- old VaR99.5
- effect of size change
- effect of mix change
- new VaR99.5

That will make the second vignette much easier to read.

---

## What else you still need for automation

These are the missing pieces I would treat as required.

### A) A common donor-pool definition

For each vignette, Python must save:

- subset used: FULL or DENSE
- eligibility filters
- whether only complete LoB reconstruction donors are used
- whether 2024 is included
- whether only adverse donors are used for tail plots
- quantile method
- bootstrap B
- KDE bandwidth rule

Otherwise the results are not reproducible.

### B) A provenance file

For each vignette, create one machine-readable metadata file containing:

- run ID
- paper version
- target profile spec
- donor pool spec
- formulas version
- size-function coefficients
- plot settings
- timestamp
- git commit or script hash

### C) Plot-data CSVs and XLSXs and TEXs

Save the underlying x-y data for every figure, not just the image.

That makes LaTeX integration and later edits much easier.

### D) Auto-generated narrative snippets

For each vignette, generate a 100–150 word caption-style summary containing:

- direction of distortion
- biggest quantile change
- whether mix or size dominated
- donor count and tail support count

That will save you a lot of manual paper editing.

---

## Recommended output manifest

For each vignette, I would have Python generate exactly this bundle:

- `target_profile.json`
- `target_profile_table.csv`
- `donor_selection.csv`
- `worked_example_size_mismatch.csv`
- `worked_example_mix_mismatch.csv`
- `distribution_stats.csv`
- `tail_support_bootstrap.csv`
- `decomposition_summary.csv`
- `distribution_plot.pdf`
- `tail_exceedance_plot.pdf`
- `distribution_plot.png`
- `tail_exceedance_plot.png`
- `distribution_plot_data.csv`
- `tail_plot_data.csv`
- `summary_snippet.md`
- `target_profile_table.xlsx`
- `donor_selection.xlsx`
- `worked_example_size_mismatch.xlsx`
- `worked_example_mix_mismatch.xlsx`
- `distribution_stats.xlsx`
- `tail_support_bootstrap.xlsx`
- `decomposition_summary.xlsx`
- `distribution_plot_data.xlsx`
- `tail_plot_data.xlsx`
- `target_profile_table.tex`
- `donor_selection.tex`
- `worked_example_size_mismatch.tex`
- `worked_example_mix_mismatch.tex`
- `distribution_stats.tex`
- `tail_support_bootstrap.tex`
- `decomposition_summary.tex`
- `distribution_plot_data.tex`
- `tail_plot_data.tex`

And for vignette 2 add:

- `profile_transition_table.csv`
- `old_to_new_change_decomposition.csv`
- `old_to_new_waterfall.png`
- `profile_transition_table.xlsx`
- `old_to_new_change_decomposition.xlsx`
- `profile_transition_table.tex`
- `old_to_new_change_decomposition.tex`

---

## spec_version: "1.0"

artifact_pack_name: "revised_vignette_pack"

description: >

  Strict generation spec for the Python pipeline that creates worked-example

  artifacts for two hypothetical syndicate vignettes in the revised paper.

  The pipeline must generate reproducible tables, figures, metadata, and

  narrative snippets for paper-ready inclusion.

global_rules:

  objective: >

```
Generate worked-example outputs that demonstrate distortion from naive

pooling of market reserve movements and the effect of transferring donor

observations onto a target portfolio basis.
```

  primary_distribution_object: "signed_pyd_ratio"

  notation:

```
S_raw: "Raw donor signed PYD ratio"

S_mix: "LoB-mix-standardised signed PYD ratio"

S_adj: "Fully adjusted signed PYD ratio after reserve-size scaling"

S_mix_old: "LoB-mix-standardised ratio for old profile"

S_adj_old: "Fully adjusted ratio for old profile"

S_mix_new: "LoB-mix-standardised ratio for new profile"

S_adj_new: "Fully adjusted ratio for new profile"
```

  main_transfer_rule:

```
step_1: "Exact LoB-mix projection"

step_2: "Reserve-size scaling"

note: >

  HHI is a concentration descriptor and diagnostic, not a separate primary

  adjustment operator in the main pipeline.
```

  distribution_conventions:

```
tail_side: "adverse"

include_negative_values_in_full_distribution_outputs: true

include_positive_values_only_in_tail_outputs: true

quantile_labels:

  q75: "Q75"

  var99: "VaR99"

  var995: "VaR99.5"
```

  reproducibility:

```
required: true

save_run_metadata: true

save_plot_data_csv: true

save_config_snapshot: true

deterministic_seed_required: true
```

inputs:

  required_files:

```
donor_observations_table:

  description: >

    Observation-level donor dataset with one row per syndicate-year and all

    fields needed for raw ratio, LoB projection, and reserve-size scaling.

  required_columns:

    - syndicate_id

    - report_year

    - observation_id

    - opening_reserves

    - signed_pyd_amount

    - signed_pyd_ratio

    - event_group_id

    - hhi

    - lob_weights_json

    - has_complete_lob_reconstruction

    - include_in_dense

    - include_in_full

donor_line_level_table:

  description: >

    Line-level donor table needed for exact projection calculations.

  required_columns:

    - observation_id

    - lob_name

    - source_weight

    - line_level_reserve_base

    - line_level_movement_amount

    - line_level_ratio

size_function_coefficients:

  description: "Calibrated coefficients for V_size(R) = A + B * R^C"

  required_fields:

    - A

    - B

    - C

vignette_targets:

  description: >

    Target portfolio definitions for vignette 1 and vignette 2 old/new

    profiles.

  required_fields:

    - vignette_id

    - profile_id

    - profile_label

    - reserve_size

    - lob_weights_json

    - hhi

pipeline_settings:

  required_fields:

    - donor_subset

    - bootstrap_reps

    - bootstrap_confidence_level

    - quantile_method

    - kde_bandwidth_rule

    - random_seed

    - include_2024

    - adverse_tail_threshold_rule
```

vignettes:

  vignette_1:

```
vignette_id: "v1_new_entrant"

narrative_role: >

  Newly established diversified syndicate with too little internal history.

target_profiles:

  - profile_id: "v1_target"

    required_fields:

      - profile_label

      - reserve_size

      - lob_weights_json

      - hhi

required_outputs:

  - target_profile_card

  - donor_selection_table

  - worked_example_size_mismatch

  - worked_example_mix_mismatch

  - distribution_plot

  - tail_exceedance_plot

  - distribution_statistics_table

  - tail_support_bootstrap_table

  - decomposition_summary_table

  - summary_snippet
```

  vignette_2:

```
vignette_id: "v2_post_exit"

narrative_role: >

  Syndicate that ceased writing one LoB, became smaller, and became more

  concentrated.

target_profiles:

  - profile_id: "v2_old_profile"

    required_fields:

      - profile_label

      - reserve_size

      - lob_weights_json

      - hhi

  - profile_id: "v2_new_profile"

    required_fields:

      - profile_label

      - reserve_size

      - lob_weights_json

      - hhi

      - dropped_lob_name

      - dropped_lob_old_weight

      - narrative_reason_label

required_outputs:

  - target_transition_card

  - donor_selection_table

  - worked_example_size_mismatch

  - worked_example_mix_mismatch

  - profile_transition_distribution_table

  - distribution_plot

  - tail_exceedance_plot

  - distribution_statistics_table

  - tail_support_bootstrap_table

  - decomposition_summary_table

  - old_to_new_change_decomposition

  - old_to_new_waterfall_plot

  - summary_snippet
```

common_eligibility_rules:

  donor_pool:

```
subset_options: ["DENSE", "FULL"]

default_subset: "FULL"

require_complete_lob_reconstruction: true

require_non_missing_opening_reserves: true

require_non_missing_signed_pyd_ratio: true

require_valid_lob_weights: true
```

  distribution_construction:

```
use_all_eligible_donors_for_full_distribution: true

tail_plots_use_positive_values_only: true
```

  diagnostics:

```
compute_hhi_for_all_targets_and_donors: true

compute_hellinger_distance_for_all_target_donor_pairs: true

compute_log_reserve_ratio_for_all_target_donor_pairs: true
```

donor_selection_rules:

  worked_example_size_mismatch:

```
goal: >

  Select one donor that strongly differs in reserve size from the target

  while keeping concentration reasonably similar.

required_conditions:

  - has_complete_lob_reconstruction == true

preference_order:

  - "positive signed_pyd_ratio preferred, but not mandatory"

  - "maximize abs(log(opening_reserves / target_reserve_size))"

  - "subject to abs(donor_hhi - target_hhi) <= 0.05 where possible"

fallback_rule: >

  If no donor satisfies the HHI tolerance, select the donor with the

  smallest abs(donor_hhi - target_hhi) among the top 10 reserve-size

  mismatches.

output_fields:

  - observation_id

  - syndicate_id

  - report_year

  - opening_reserves

  - signed_pyd_amount

  - signed_pyd_ratio

  - hhi

  - hellinger_distance

  - log_reserve_ratio_to_target
```

  worked_example_mix_mismatch:

```
goal: >

  Select one donor that strongly differs in concentration / mix from the

  target while keeping reserve size reasonably similar.

required_conditions:

  - has_complete_lob_reconstruction == true

preference_order:

  - "positive signed_pyd_ratio preferred, but not mandatory"

  - "maximize hellinger_distance(target_weights, donor_weights)"

  - "subject to 0.67 <= donor_reserves / target_reserve_size <= 1.5 where possible"

fallback_rule: >

  If no donor satisfies the reserve-size similarity band, select the donor

  with the smallest abs(log(opening_reserves / target_reserve_size)) among

  the top 10 mix mismatches.

output_fields:

  - observation_id

  - syndicate_id

  - report_year

  - opening_reserves

  - signed_pyd_amount

  - signed_pyd_ratio

  - hhi

  - hellinger_distance

  - log_reserve_ratio_to_target
```

calculation_rules:

  raw_ratio:

```
formula: "S_raw = signed_pyd_amount / opening_reserves"
```

  mix_projection:

```
formula: "S_mix = sum_over_lob(target_weight_l * donor_line_level_ratio_l)"

per_lob_required_fields:

  - lob_name

  - source_weight

  - target_weight

  - line_level_ratio

  - projected_contribution

handling_rules:

  unobserved_target_lob_in_donor: "set donor line_level_ratio to 0"

  source_weight_floor: 0.01

  line_level_ratio_cap_abs: 5.0
```

  size_adjustment:

```
size_function: "V_size(R) = A + B * R^C"

multiplier_formula: "lambda = sqrt(V_size(target_reserve_size) / V_size(donor_reserve_size))"

final_formula: "S_adj = S_mix * lambda"
```

  concentration_diagnostics:

```
compute_for_each_profile: true

fields:

  - hhi

  - hellinger_distance

  - reserve_ratio

  - log_reserve_ratio
```

  change_metrics:

```
raw_to_mix_abs: "S_mix - S_raw"

mix_to_adj_abs: "S_adj - S_mix"

raw_to_adj_abs: "S_adj - S_raw"

raw_to_mix_pct: "(S_mix - S_raw) / abs(S_raw) if S_raw != 0 else null"

mix_to_adj_pct: "(S_adj - S_mix) / abs(S_mix) if S_mix != 0 else null"

raw_to_adj_pct: "(S_adj - S_raw) / abs(S_raw) if S_raw != 0 else null"
```

statistics_rules:

  distribution_rows_v1:

```
- raw_market

- adjusted_target
```

  distribution_rows_v2:

```
- raw_market

- adjusted_old_profile

- adjusted_new_profile

- delta_old_to_new
```

  required_statistics:

```
- n_total

- n_adverse

- mean

- standard_deviation

- q75

- var99

- var995
```

  delta_fields:

```
absolute_delta_required: true

percentage_delta_required: true
```

  quantile_method:

```
source: "pipeline_settings.quantile_method"

must_be_recorded_in_metadata: true
```

bootstrap_rules:

  required: true

  resampling_unit: "syndicate_id"

  preserve_within_syndicate_dependence: true

  repetitions_field: "pipeline_settings.bootstrap_reps"

  confidence_level_field: "pipeline_settings.bootstrap_confidence_level"

  outputs_required:

```
- var99_point_estimate

- var99_ci_lower

- var99_ci_upper

- var99_tail_support_count

- var995_point_estimate

- var995_ci_lower

- var995_ci_upper

- var995_tail_support_count
```

decomposition_rules:

  vignette_1:

```
required: true

compare:

  baseline: "raw_market"

  target: "adjusted_target"

components:

  - mix_effect

  - size_effect

method: "shapley"

required_output_fields:

  - raw_metric

  - mix_adjusted_metric

  - fully_adjusted_metric

  - mix_effect

  - size_effect
```

  vignette_2:

```
required: true

compare:

  baseline: "adjusted_old_profile"

  target: "adjusted_new_profile"

components:

  - mix_change_effect

  - size_change_effect

method: "shapley"

intermediate_states_required:

  - old_mix_old_size

  - old_mix_new_size

  - new_mix_old_size

  - new_mix_new_size

required_output_fields:

  - old_profile_metric

  - new_profile_metric

  - mix_change_effect

  - size_change_effect
```

figure_specifications:

  distribution_plot:

```
required: true

format: ["pdf", "png"]

x_variable: "signed_pyd_ratio"

y_variable: "density"

series_v1:

  - raw_market

  - adjusted_target

series_v2:

  - raw_market

  - adjusted_old_profile

  - adjusted_new_profile

allowed_rendering: ["histogram", "kde", "histogram_plus_kde"]

rendering_choice_field: "pipeline_settings.distribution_plot_mode"

shared_x_limits_within_vignette: true

vertical_markers:

  - mean

  - q75

  - var99

  - var995

subtitle_required_fields:

  - donor_subset

  - n_total

  - n_adverse

save_underlying_plot_data_csv: true
```

  tail_exceedance_plot:

```
required: true

format: ["pdf", "png"]

x_variable: "signed_pyd_ratio_positive_only"

y_variable: "empirical_exceedance_probability"

series_v1:

  - raw_market

  - adjusted_target

series_v2:

  - raw_market

  - adjusted_old_profile

  - adjusted_new_profile

markers_required:

  - var99

  - var995

save_underlying_plot_data_csv: true
```

  old_to_new_waterfall_plot:

```
required_for_vignette_2: true

format: ["pdf", "png"]

bars_required:

  - old_profile_metric

  - size_change_effect

  - mix_change_effect

  - new_profile_metric

metric_default: "var995"

save_underlying_plot_data_csv: true
```

table_specifications:

  target_profile_card:

```
required_for: ["vignette_1"]

format: ["csv", "json"]

required_fields:

  - vignette_id

  - profile_id

  - profile_label

  - reserve_size

  - lob_weights_json

  - hhi

  - donor_subset

  - donor_count

  - adverse_donor_count

  - tail_support_count_var99

  - tail_support_count_var995
```

  target_transition_card:

```
required_for: ["vignette_2"]

format: ["csv", "json"]

required_fields:

  - vignette_id

  - old_profile_label

  - new_profile_label

  - old_reserve_size

  - new_reserve_size

  - old_lob_weights_json

  - new_lob_weights_json

  - old_hhi

  - new_hhi

  - dropped_lob_name

  - dropped_lob_old_weight

  - reserve_size_pct_change

  - hhi_change

  - narrative_reason_label

  - donor_subset

  - donor_count

  - adverse_donor_count
```

  donor_selection_table:

```
required_for: ["vignette_1", "vignette_2"]

format: ["csv", "xlsx", "tex"]

required_rows:

  - worked_example_size_mismatch

  - worked_example_mix_mismatch

required_fields:

  - selection_type

  - observation_id

  - syndicate_id

  - report_year

  - opening_reserves

  - signed_pyd_amount

  - signed_pyd_ratio

  - hhi

  - hellinger_distance

  - log_reserve_ratio_to_target

  - selection_reason
```

  worked_example_table:

```
required_for: ["vignette_1", "vignette_2"]

output_names:

  size_mismatch: "worked_example_size_mismatch"

  mix_mismatch: "worked_example_mix_mismatch"

format: ["csv", "json"]

required_sections:

  summary_fields:

    - vignette_id

    - target_profile_id

    - donor_observation_id

    - donor_syndicate_id

    - donor_report_year

    - donor_reserve_size

    - donor_hhi

    - donor_signed_pyd_amount

    - donor_signed_pyd_ratio

    - target_reserve_size

    - target_hhi

    - S_raw

    - S_mix

    - S_adj

    - raw_to_mix_abs

    - mix_to_adj_abs

    - raw_to_adj_abs

    - raw_to_mix_pct

    - mix_to_adj_pct

    - raw_to_adj_pct

    - size_multiplier_lambda

    - V_size_donor

    - V_size_target

  per_lob_fields:

    - lob_name

    - source_weight

    - target_weight

    - line_level_ratio

    - projected_contribution
```

  distribution_statistics_table:

```
required_for: ["vignette_1", "vignette_2"]

format: ["csv", "xlsx", "tex"]

required_fields:

  - distribution_label

  - n_total

  - n_adverse

  - mean

  - standard_deviation

  - q75

  - var99

  - var995

  - abs_delta_vs_baseline

  - pct_delta_vs_baseline
```

  tail_support_bootstrap_table:

```
required_for: ["vignette_1", "vignette_2"]

format: ["csv", "xlsx", "tex"]

required_fields:

  - distribution_label

  - metric

  - point_estimate

  - ci_lower

  - ci_upper

  - tail_support_count

  - bootstrap_reps

  - confidence_level
```

  decomposition_summary_table:

```
required_for: ["vignette_1", "vignette_2"]

format: ["csv", "xlsx", "tex"]

required_fields_v1:

  - metric

  - raw_metric

  - mix_adjusted_metric

  - fully_adjusted_metric

  - mix_effect

  - size_effect

required_fields_v2:

  - metric

  - old_profile_metric

  - new_profile_metric

  - mix_change_effect

  - size_change_effect
```

  profile_transition_distribution_table:

```
required_for: ["vignette_2"]

format: ["csv", "xlsx", "tex"]

required_fields:

  - donor_observation_id

  - S_raw

  - S_mix_old

  - S_adj_old

  - S_mix_new

  - S_adj_new
```

narrative_outputs:

  summary_snippet:

```
required: true

format: ["md", "txt"]

word_count_range: [100, 150]

required_content:

  - direction_of_distortion

  - largest_quantile_change

  - whether_mix_or_size_dominated

  - donor_count

  - tail_support_counts

  - one_sentence_interpretation_for_paper
```

output_bundle:

  root_directory_pattern: "paper_pack/{run_id}/{vignette_id}/"

  required_files_vignette_1:

```
- target_profile.json

- target_profile_table.csv

- donor_selection.csv

- worked_example_size_mismatch.csv

- worked_example_mix_mismatch.csv

- distribution_statistics.csv

- tail_support_bootstrap.csv

- decomposition_summary.csv

- distribution_plot.pdf

- distribution_plot.png

- tail_exceedance_plot.pdf

- tail_exceedance_plot.png

- distribution_plot_data.csv

- tail_exceedance_plot_data.csv

- summary_[snippet.md](http://snippet.md)

- metadata.json
```

  required_files_vignette_2:

```
- target_transition.json

- target_transition_table.csv

- donor_selection.csv

- worked_example_size_mismatch.csv

- worked_example_mix_mismatch.csv

- profile_transition_distribution.csv

- distribution_statistics.csv

- tail_support_bootstrap.csv

- decomposition_summary.csv

- old_to_new_change_decomposition.csv

- distribution_plot.pdf

- distribution_plot.png

- tail_exceedance_plot.pdf

- tail_exceedance_plot.png

- old_to_new_waterfall_plot.pdf

- old_to_new_waterfall_plot.png

- distribution_plot_data.csv

- tail_exceedance_plot_data.csv

- old_to_new_waterfall_plot_data.csv

- summary_[snippet.md](http://snippet.md)

- metadata.json
```

metadata_spec:

  required_fields:

```
- run_id

- spec_version

- paper_version_label

- git_commit_or_hash

- execution_timestamp_utc

- random_seed

- donor_subset

- include_2024

- bootstrap_reps

- bootstrap_confidence_level

- quantile_method

- kde_bandwidth_rule

- size_function_A

- size_function_B

- size_function_C

- distribution_plot_mode

- environment_python_version

- environment_package_lock_hash
```

validation_checks:

  required:

```
- "All target LoB weights must sum to 1.0 within tolerance 1e-9"

- "All donor LoB weights used in projection must sum to 1.0 within tolerance 1e-9 after preprocessing"

- "All reserve sizes must be strictly positive"

- "All V_size(R) outputs must be strictly positive"

- "All selected worked-example donors must satisfy eligibility rules"

- "All figures must have matching plot-data CSVs"

- "All tables must include required columns"

- "All quantiles must be computed using recorded quantile method"

- "All bootstrap tables must include tail support counts"

- "All outputs must be written under the root_directory_pattern"
```

  fail_fast: true

json_schema_guidance:

  note: >

```
This YAML spec is canonical. The Python pipeline may convert it to JSON for

internal validation, but field names, nesting, and required outputs must be

preserved exactly.
```

