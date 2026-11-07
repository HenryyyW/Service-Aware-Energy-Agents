# Thermal-comfort reporting (and why it is unmeasurable here)

The stock CityLearn 2022 dataset ships `indoor_dry_bulb_temperature`
(and the two other comfort series) **all-NaN**, so the comfort metric defined
in `src/evaluation/metrics.py` degrades to 0.0: a NaN indoor temperature fails
both band comparisons and never accumulates a violation.

Measured across the 250 B-axis runs: `comfort_violation_degree_hours` is
**0.0 in every run** (25 scenario/controller cells), min =
max = 0.0. That is a
**data-availability result, not a comfort-satisfaction result** -- the paper
must not present it as "no comfort violations".

The 2026-11-07 comfort fill (`705923481`: substitute 22.0 degC, inside the
[20, 25] band, only when the column is entirely NaN) keeps the metric at
exactly the same 0.0 as the pre-fix runs while making the observation space
constructible on gymnasium >= 1.1. It does **not** create comfort data.

To make any comfort claim the paper needs a dataset with real indoor
temperature (or a CityLearn comfort subsystem with a building model); until
then comfort should be listed as out of scope with this reason.
