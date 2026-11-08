"""Community aggregator agent for multi-agent coordination."""

from typing import Optional, List, Dict, Any
import os
import random

from src.coordination.base import (
    CoordinationAgent,
    CoordinationMessage,
    CoordinationPhase,
    BuildingProposal,
    AggregationResult,
    BatteryProposal,
    EVProposal,
    Proposal,
)
from src.schemas.scenario import ScenarioConfig


class ProposerCorruption:
    """Handles hostile proposer injection for M2b experiment.

    Injects deterministic out-of-bounds corruptions into parsed proposals
    when SAEA_LLM_HOSTILE=out_of_bounds is set.
    """

    def __init__(self, timestep: int, seed: int = 42):
        self.enabled = os.environ.get("SAEA_LLM_HOSTILE") == "out_of_bounds"
        self.mode = "out_of_bounds"  # only mode for now
        self.timestep = timestep
        self.seed = seed

        # Deterministic RNG per timestep
        self.rng = random.Random(seed + timestep)

        # Corruption factor: scale beyond device limits (ensure exceeding limit)
        # Use a factor that guarantees exceeding max limit: (max/requested) + buffer
        self.corruption_factor = 2.5

        # Measurement tracking
        self.stats = {
            "total_proposals_corrupted": 0,
            "battery_corrupted": 0,
            "ev_corrupted": 0,
            "flexible_load_corrupted": 0,
            "total_power_increase_kw": 0.0,
        }

        # Repair tracking (populated by verifier/repair loop)
        self.repair_success_count = 0
        self.repair_total_count = 0
        self.unsafe_patch_accepted = 0
        self.post_repair_regressions = []
        self.execution_cost_usd = 0.0

    def corrupt_proposal(self, proposal: Proposal) -> Proposal:
        """Corrupt a proposal by scaling its power beyond device limits.

        Returns a new corrupted proposal (original unchanged).
        """
        if not self.enabled:
            return proposal

        # Check if this proposal type has limits we can exceed
        max_limit = self._get_max_limit(proposal)
        if max_limit is None or max_limit <= 0:
            return proposal

        requested = proposal.requested_power_kw

        # Determine direction and limit
        if requested > 0:
            # Positive: charging/consuming - limit is max_charge_kw
            limit = max_limit
            min_corrupted = limit * 1.2
            corrupted_power = max(requested * self.corruption_factor, min_corrupted)
        elif requested < 0:
            # Negative: discharging/generating - limit is max_discharge_kw
            limit = max_limit
            min_corrupted = -limit * 1.2  # more negative
            corrupted_power = min(requested * self.corruption_factor, min_corrupted)
        else:
            return proposal  # zero power, nothing to corrupt

        # Track stats
        self.stats["total_proposals_corrupted"] += 1
        self.stats["total_power_increase_kw"] += abs(corrupted_power - requested)

        if isinstance(proposal, BatteryProposal):
            self.stats["battery_corrupted"] += 1
        elif isinstance(proposal, EVProposal):
            self.stats["ev_corrupted"] += 1
        elif isinstance(proposal, Proposal) and "max_power" in proposal.constraints:
            self.stats["flexible_load_corrupted"] += 1

        # Create corrupted copy
        corrupted = Proposal(
            agent_id=proposal.agent_id,
            asset_id=proposal.asset_id,
            requested_power_kw=corrupted_power,
            priority=proposal.priority,
            constraints=proposal.constraints.copy(),
            metadata={
                **proposal.metadata,
                "corrupted": True,
                "original_power_kw": requested,
            },
        )
        return corrupted

    def _get_max_limit(self, proposal: Proposal) -> Optional[float]:
        """Get the device max limit from proposal constraints."""
        if isinstance(proposal, BatteryProposal):
            return (
                proposal.max_charge_kw
                or proposal.max_discharge_kw
                or proposal.constraints.get("power_kw")
            )
        elif isinstance(proposal, EVProposal):
            return proposal.max_charge_kw or proposal.constraints.get("max_charge_kw")
        elif isinstance(proposal, Proposal):
            return proposal.constraints.get("max_power") or proposal.constraints.get(
                "power_kw"
            )
        return None

    def corrupt_building_proposal(self, proposal: BuildingProposal) -> BuildingProposal:
        """Corrupt all sub-proposals in a building proposal."""
        if not self.enabled:
            return proposal

        # Corrupt battery proposal
        battery_corrupted = proposal.battery_proposal
        if battery_corrupted:
            battery_corrupted = self.corrupt_proposal(battery_corrupted)

        # Corrupt EV proposals
        ev_corrupted = [self.corrupt_proposal(ev) for ev in proposal.ev_proposals]

        # Corrupt flexible load proposals
        fl_corrupted = [
            self.corrupt_proposal(fl) for fl in proposal.flexible_load_proposals
        ]

        # Create corrupted building proposal
        return BuildingProposal(
            agent_id=proposal.agent_id,
            asset_id=proposal.asset_id,
            building_id=proposal.building_id,
            requested_power_kw=proposal.requested_power_kw,  # building total not corrupted here
            priority=proposal.priority,
            constraints=proposal.constraints.copy(),
            battery_proposal=battery_corrupted,
            ev_proposals=ev_corrupted,
            flexible_load_proposals=fl_corrupted,
            net_demand_kw=proposal.net_demand_kw,
            pv_generation_kw=proposal.pv_generation_kw,
            metadata={**proposal.metadata, "corrupted": True},
        )

    def record_repair_result(
        self,
        success: bool,
        unsafe_patch: bool = False,
        regression: Optional[Dict] = None,
        cost_usd: float = 0.0,
    ):
        """Record repair loop outcome for measurement hooks."""
        self.repair_total_count += 1
        if success:
            self.repair_success_count += 1
        if unsafe_patch:
            self.unsafe_patch_accepted += 1
        if regression:
            self.post_repair_regressions.append(regression)
        self.execution_cost_usd += cost_usd

    def get_metrics(self) -> Dict[str, Any]:
        """Get all measurement hooks for result.json."""
        return {
            "hostile_mode": self.enabled,
            "hostile_mode_type": self.mode if self.enabled else None,
            "corruption_factor": self.corruption_factor if self.enabled else None,
            "total_proposals_corrupted": self.stats["total_proposals_corrupted"],
            "battery_corrupted": self.stats["battery_corrupted"],
            "ev_corrupted": self.stats["ev_corrupted"],
            "flexible_load_corrupted": self.stats["flexible_load_corrupted"],
            "total_power_increase_kw": self.stats["total_power_increase_kw"],
            "repair_success_rate": (
                self.repair_success_count / self.repair_total_count
                if self.repair_total_count > 0
                else None
            ),
            "unsafe_patch_acceptance": (
                self.unsafe_patch_accepted / self.repair_total_count
                if self.repair_total_count > 0
                else None
            ),
            "post_repair_regressions_count": len(self.post_repair_regressions),
            "post_repair_regressions": self.post_repair_regressions,
            "execution_cost_usd": self.execution_cost_usd,
        }


class CommunityAggregator(CoordinationAgent):
    """Community aggregator for hierarchical coordination.

    Responsible for:
    - Collecting building-level proposals
    - Reconciling proposals with community grid limits
    - Performing grid-constraint validation via pandapower
    - Producing final allocations
    """

    def __init__(self, scenario_config: ScenarioConfig, pandapower_network=None):
        super().__init__("community_aggregator")
        self.scenario_config = scenario_config
        self.pandapower_network = pandapower_network

        # State
        self.building_proposals: Dict[str, BuildingProposal] = {}
        self.final_allocations: Dict[str, BuildingProposal] = {}
        self.iteration = 0
        self.max_iterations = 3

        # Grid limits
        self.community_import_limit = (
            scenario_config.community_import_limit_kw or float("inf")
        )
        self.community_export_limit = (
            scenario_config.community_export_limit_kw or float("inf")
        )

        # Hostile mode tracking
        self._last_corruptor: Optional[ProposerCorruption] = None

    def propose(self, context: Dict[str, Any]) -> CoordinationMessage:
        """Not used for aggregator - it receives proposals instead."""
        return self.send_message(
            receiver="broadcast",
            phase=CoordinationPhase.AGGREGATOR_RECONCILIATION,
            payload={"status": "waiting_for_proposals"},
        )

    def receive(self, message: CoordinationMessage) -> Optional[CoordinationMessage]:
        """Receive building proposals and trigger reconciliation when all received."""
        if message.phase == CoordinationPhase.LOCAL_PROPOSAL:
            proposal = message.payload.get("proposal")
            building_id = message.payload.get("building_id")

            if proposal and building_id:
                self.building_proposals[building_id] = proposal

                # Check if all buildings have proposed
                expected_buildings = [
                    b.building_id for b in self.scenario_config.buildings
                ]
                if len(self.building_proposals) >= len(expected_buildings):
                    # All proposals received, reconciliation will be triggered by coordinator
                    pass

        return None

    def _reconcile_proposals(self, timestep: int = 0) -> Optional[CoordinationMessage]:
        """Reconcile building proposals with community limits."""

        # Apply hostile proposer corruption if enabled
        corruptor = ProposerCorruption(
            timestep=timestep, seed=self.scenario_config.random_seed
        )
        corrupted_proposals = {}
        for building_id, proposal in self.building_proposals.items():
            corrupted_proposals[building_id] = corruptor.corrupt_building_proposal(
                proposal
            )

        # Store corruptor for metrics collection
        self._last_corruptor = corruptor

        # Use corrupted proposals for reconciliation
        proposals_to_use = (
            corrupted_proposals if corruptor.enabled else self.building_proposals
        )

        # Calculate total import/export
        total_import = sum(
            max(0, p.requested_power_kw) for p in proposals_to_use.values()
        )
        total_export = sum(
            -min(0, p.requested_power_kw) for p in proposals_to_use.values()
        )

        # Create initial allocations (copy proposals)
        self.final_allocations = {}
        adjustments = []

        for building_id, proposal in proposals_to_use.items():
            # Start with requested values
            allocated_proposal = BuildingProposal(
                agent_id=proposal.agent_id,
                asset_id=proposal.asset_id,
                building_id=proposal.building_id,
                requested_power_kw=proposal.requested_power_kw,
                priority=proposal.priority,
                constraints=proposal.constraints.copy(),
                battery_proposal=proposal.battery_proposal,
                ev_proposals=proposal.ev_proposals,
                flexible_load_proposals=proposal.flexible_load_proposals,
                net_demand_kw=proposal.net_demand_kw,
                pv_generation_kw=proposal.pv_generation_kw,
            )
            self.final_allocations[building_id] = allocated_proposal

        # Apply community import limit
        if total_import > self.community_import_limit:
            scale = self.community_import_limit / total_import
            adjustments.append(
                {
                    "type": "import_limit",
                    "limit": self.community_import_limit,
                    "requested": total_import,
                    "scale_factor": scale,
                }
            )
            self._scale_allocations(scale, positive_only=True)
            total_import = self.community_import_limit

        # Apply community export limit
        if total_export > self.community_export_limit:
            scale = self.community_export_limit / total_export
            adjustments.append(
                {
                    "type": "export_limit",
                    "limit": self.community_export_limit,
                    "requested": total_export,
                    "scale_factor": scale,
                }
            )
            self._scale_allocations(scale, positive_only=False)
            total_export = self.community_export_limit

        # Run grid validation if pandapower network available
        grid_valid = True
        grid_violations = []

        if self.pandapower_network is not None:
            grid_valid, grid_violations = self._validate_grid()
            if not grid_valid:
                # Apply grid constraint adjustments
                adjusted_allocations, grid_adjustments = self._apply_grid_constraints(
                    grid_violations
                )
                self.final_allocations = adjusted_allocations
                adjustments.extend(grid_adjustments)

        result = AggregationResult(
            building_allocations=self.final_allocations,
            total_import_kw=total_import,
            total_export_kw=total_export,
            grid_constraints_satisfied=grid_valid,
            adjustments_made=adjustments,
        )

        # Send allocations to building agents
        messages = []
        for building_id, allocation in self.final_allocations.items():
            msg = self.send_message(
                receiver=f"building_{building_id}",
                phase=CoordinationPhase.FINAL_ALLOCATION,
                payload={"allocation": allocation},
            )
            messages.append(msg)

        # Return first message (in real implementation, would send all)
        return messages[0] if messages else None

    def _scale_allocations(self, scale: float, positive_only: bool):
        """Scale allocation power values."""
        for allocation in self.final_allocations.values():
            # Scale battery
            if allocation.battery_proposal:
                if positive_only and allocation.battery_proposal.requested_power_kw > 0:
                    allocation.battery_proposal.requested_power_kw *= scale
                elif (
                    not positive_only
                    and allocation.battery_proposal.requested_power_kw < 0
                ):
                    allocation.battery_proposal.requested_power_kw *= scale

            # Scale EVs
            for ev_prop in allocation.ev_proposals:
                if positive_only and ev_prop.requested_power_kw > 0:
                    ev_prop.requested_power_kw *= scale
                elif not positive_only and ev_prop.requested_power_kw < 0:
                    ev_prop.requested_power_kw *= scale

            # Scale flexible loads
            for fl_prop in allocation.flexible_load_proposals:
                if positive_only and fl_prop.requested_power_kw > 0:
                    fl_prop.requested_power_kw *= scale
                elif not positive_only and fl_prop.requested_power_kw < 0:
                    fl_prop.requested_power_kw *= scale

            # Recalculate total
            battery_p = (
                allocation.battery_proposal.requested_power_kw
                if allocation.battery_proposal
                else 0
            )
            ev_p = sum(p.requested_power_kw for p in allocation.ev_proposals)
            fl_p = sum(p.requested_power_kw for p in allocation.flexible_load_proposals)
            allocation.requested_power_kw = (
                allocation.net_demand_kw + battery_p + ev_p + fl_p
            )

    def _validate_grid(self) -> tuple:
        """Validate allocations against grid constraints using pandapower."""
        if self.pandapower_network is None:
            return True, []

        try:
            import pandapower as pp

            # Map building allocations to grid buses
            # This is simplified - real implementation would use proper mapping
            net = self.pandapower_network

            # Apply loads to network
            for i, (building_id, allocation) in enumerate(
                self.final_allocations.items()
            ):
                if i < len(net.load):
                    net.load.at[i, "p_mw"] = allocation.requested_power_kw / 1000.0

            # Run power flow
            pp.runpp(net)

            # Check voltage violations
            violations = []
            vm_pu = net.res_bus.vm_pu.values
            if (vm_pu > 1.05).any() or (vm_pu < 0.95).any():
                violations.append(
                    {
                        "type": "voltage",
                        "max_voltage": float(vm_pu.max()),
                        "min_voltage": float(vm_pu.min()),
                        "buses_violated": [
                            int(i) for i, v in enumerate(vm_pu) if v > 1.05 or v < 0.95
                        ],
                    }
                )
                return False, violations

            # Check line loading
            if hasattr(net, "res_line") and len(net.res_line) > 0:
                loading = net.res_line.loading_percent.values
                if (loading > 100).any():
                    violations.append(
                        {
                            "type": "line_loading",
                            "max_loading": float(loading.max()),
                            "lines_violated": [
                                int(i) for i, l in enumerate(loading) if l > 100
                            ],
                        }
                    )
                    return False, violations

            return True, []

        except Exception as e:
            # If power flow fails, consider it a violation
            return False, [{"type": "power_flow_failed", "error": str(e)}]

    def _apply_grid_constraints(self, violations: List[Dict[str, Any]]) -> tuple:
        """Adjust allocations to resolve grid violations."""
        adjusted = {}
        adjustments = []

        for building_id, allocation in self.final_allocations.items():
            adjusted[building_id] = BuildingProposal(
                agent_id=allocation.agent_id,
                asset_id=allocation.asset_id,
                building_id=allocation.building_id,
                requested_power_kw=allocation.requested_power_kw,
                priority=allocation.priority,
                constraints=allocation.constraints.copy(),
                battery_proposal=allocation.battery_proposal,
                ev_proposals=allocation.ev_proposals,
                flexible_load_proposals=allocation.flexible_load_proposals,
                net_demand_kw=allocation.net_demand_kw,
                pv_generation_kw=allocation.pv_generation_kw,
            )

        for violation in violations:
            if violation["type"] == "voltage":
                # Reduce export (negative power) or increase import to fix voltage
                # Simplified: scale all allocations
                scale = 0.9
                for alloc in adjusted.values():
                    if alloc.battery_proposal:
                        alloc.battery_proposal.requested_power_kw *= scale
                    for ev in alloc.ev_proposals:
                        ev.requested_power_kw *= scale
                    for fl in alloc.flexible_load_proposals:
                        fl.requested_power_kw *= scale

                    # Recalculate
                    battery_p = (
                        alloc.battery_proposal.requested_power_kw
                        if alloc.battery_proposal
                        else 0
                    )
                    ev_p = sum(p.requested_power_kw for p in alloc.ev_proposals)
                    fl_p = sum(
                        p.requested_power_kw for p in alloc.flexible_load_proposals
                    )
                    alloc.requested_power_kw = (
                        alloc.net_demand_kw + battery_p + ev_p + fl_p
                    )

                adjustments.append(
                    {"type": "voltage_mitigation", "scale_factor": scale}
                )

            elif violation["type"] == "line_loading":
                # Reduce power to fix line loading
                scale = 0.85
                for alloc in adjusted.values():
                    if alloc.battery_proposal:
                        alloc.battery_proposal.requested_power_kw *= scale
                    for ev in alloc.ev_proposals:
                        ev.requested_power_kw *= scale
                    for fl in alloc.flexible_load_proposals:
                        fl.requested_power_kw *= scale

                    battery_p = (
                        alloc.battery_proposal.requested_power_kw
                        if alloc.battery_proposal
                        else 0
                    )
                    ev_p = sum(p.requested_power_kw for p in alloc.ev_proposals)
                    fl_p = sum(
                        p.requested_power_kw for p in alloc.flexible_load_proposals
                    )
                    alloc.requested_power_kw = (
                        alloc.net_demand_kw + battery_p + ev_p + fl_p
                    )

                adjustments.append(
                    {"type": "line_loading_mitigation", "scale_factor": scale}
                )

        return adjusted, adjustments

    def reset(self):
        super().reset()
        self.building_proposals = {}
        self.final_allocations = {}
        self.iteration = 0
