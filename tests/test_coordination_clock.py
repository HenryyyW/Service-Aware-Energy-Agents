"""Multi-agent coordination agents must use the real simulation resolution.

Regression: every coordination agent hardcoded 15-min steps
(hour_of_day = timestep * 0.25) while the dataset adapter overrides the
simulation to hourly resolution, so EV connection windows drifted 4x off the
simulator's actual departures and multi_agent scored ev_completion_rate 0.000
in every matrix run.
"""
from src.coordination.ev_agent import EVAgent
from src.schemas.scenario import EVConfig


def test_ev_agent_clock_follows_hours_per_step():
    ev = EVAgent(
        "ev_test",
        EVConfig(
            capacity_kwh=60.0,
            max_charge_kw=11.0,
            arrival_time="08:00",
            departure_time="12:00",
            target_soc=0.9,
            initial_soc=0.1,
        ),
    )
    # Hourly steps (the dataset adapter's resolution): step 9 is 09:00.
    hourly_context = {"observations": {}, "timestep": 9, "hours_per_step": 1.0}
    ev.propose(hourly_context)
    assert ev.connected is True

    # The old hardcoded 0.25 h/step would call step 9 "02:15" (not connected).
    legacy_context = {"observations": {}, "timestep": 9, "hours_per_step": 0.25}
    ev.propose(legacy_context)
    assert ev.connected is False


def test_ev_agent_charges_when_connected_under_hourly_steps():
    ev = EVAgent(
        "ev_test",
        EVConfig(
            capacity_kwh=60.0,
            max_charge_kw=11.0,
            arrival_time="08:00",
            departure_time="12:00",
            target_soc=0.9,
            initial_soc=0.1,
        ),
    )
    message = ev.propose({"observations": {}, "timestep": 9, "hours_per_step": 1.0})
    proposal = message.payload.get("proposal")
    assert proposal is not None
    assert proposal.requested_power_kw > 0.0, (
        "a connected, below-target EV must request charging at hourly steps"
    )
