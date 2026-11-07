# Service-level constraint definitions (as implemented)

| Constraint | Metric / field | Definition in code | Reporting status |
|---|---|---|---|
| EV departure charge | `service.ev_completion_rate` | fraction of EV departure events whose realised SOC at departure meets the required SOC (`src/evaluation/metrics.py` EV block) | reported per scenario/controller |
| EV margin | `service.ev_avg_soc_at_departure`, `ev_worst_soc_at_departure` | mean / worst realised SOC at departure across departure events | reported per scenario/controller |
| Thermal comfort | `service.comfort_violation_degree_hours` | sum over building-steps of hours outside the [20, 25] degC indoor band, from the `{building}_indoor_dry_bulb_temperature` observation | **unmeasurable on the stock dataset** (see comfort_report.md) |
| Flexible-load completion | `service.flexible_load_completion_rate`, `flexible_load_avg_delay_hours` | deferrable-appliance cycles finished inside their window / mean delay in hours | reported (all runs 0 completion on the stock schedule) |
| Demand response | `service.dr_requested_kw`, `dr_delivered_kw`, `dr_credited_kw` | requested vs delivered vs credited DR kW | reported (0 in the B-axis matrices) |
| Cost coverage under failure | `service.member_cost_coverage`, `energy.cost_coverage` | share of member-steps with measurable cost (scenario E blanks the failed member's cost) | reported |
| Community import/export limits | `community_import_limit_kw`, `community_export_limit_kw` + `failure_injector` grid-limit failure | hard community exchange limits; violations logged as `export_limit_*` / `import_limit_*` diagnostics | reported |
| Voltage / line / transformer limits | `grid.voltage_violations_count`, `line_loading_violations`, `transformer_loading_violations` | pandapower power-flow check per step | reported |
