"""Report generation API endpoints."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import json
import io

from app.routers.simulations import _runs, _couplers

router = APIRouter()


class ReportRequest(BaseModel):
    run_id: str
    format: str = "markdown"  # markdown, html, json
    include_sections: Optional[list[str]] = None


@router.get("/reports/{run_id}")
async def get_report(run_id: str):
    """Get simulation report as markdown text."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run = _runs[run_id]
    
    # Try to get from agent task first (if available)
    from app.routers.agent import _tasks
    for task in _tasks.values():
        if task.get("run_id") == run_id and task.get("report"):
            return Response(content=task["report"], media_type="text/markdown")
    
    # Generate report from simulation results
    report = _generate_report(run)
    return Response(content=report, media_type="text/markdown")


@router.get("/reports/{run_id}/download")
async def download_report(run_id: str, format: str = Query("markdown")):
    """Download report in specified format."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run = _runs[run_id]
    report_content = _generate_report(run)
    
    if format == "markdown":
        filename = f"report_{run_id}.md"
        media_type = "text/markdown"
        content = report_content
    elif format == "json":
        filename = f"report_{run_id}.json"
        media_type = "application/json"
        content = json.dumps(_generate_report_json(run), indent=2)
    elif format == "html":
        filename = f"report_{run_id}.html"
        media_type = "text/html"
        content = _markdown_to_html(report_content)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
    
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _generate_report(run: dict) -> str:
    """Generate markdown report from run data."""
    lines = [
        f"# Simulation Report: {run['run_id']}",
        "",
        f"**Scenario:** {run['scenario_id']}  ",
        f"**Controller:** {run['controller_type']}  ",
        f"**Status:** {run['status']}  ",
        f"**Start Time:** {run['start_time']}  ",
        f"**End Time:** {run.get('end_time', 'N/A')}  ",
        f"**Random Seed:** {run.get('random_seed', 'N/A')}  ",
        "",
        "---",
        "",
        "## Energy Metrics",
        "",
    ]
    
    em = run.get("energy_metrics", {})
    if em:
        lines.extend([
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Cost | ${em.get('total_cost', 0):.2f} |",
            f"| Grid Import | {em.get('grid_import_kwh', 0):.2f} kWh |",
            f"| Grid Export | {em.get('grid_export_kwh', 0):.2f} kWh |",
            f"| Peak Demand | {em.get('peak_demand_kw', 0):.2f} kW |",
            f"| PV Self-Consumption | {em.get('pv_self_consumption', 0):.2%} |",
            f"| PV Generation | {em.get('pv_generation_kwh', 0):.2f} kWh |",
            f"| PV Curtailment | {em.get('pv_curtailment', 0):.2f} kWh |",
            f"| Battery Throughput | {em.get('battery_throughput_kwh', 0):.2f} kWh |",
            f"| Carbon Emissions | {em.get('carbon_emissions_kg', 0):.2f} kg CO₂ |",
            "",
        ])
    
    lines.append("## Service Metrics")
    lines.append("")
    
    sm = run.get("service_metrics", {})
    if sm:
        lines.extend([
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| EV Completion Rate | {sm.get('ev_completion_rate', 0):.2%} |",
            f"| Avg EV SOC at Departure | {sm.get('avg_ev_soc_at_departure', 0):.2%} |",
            f"| Comfort Violation (degree-hours) | {sm.get('comfort_violation_degree_hours', 0):.2f} |",
            f"| Flexible Load Completion Rate | {sm.get('flexible_load_completion_rate', 0):.2%} |",
            f"| DR Delivery Rate | {sm.get('dr_delivery_rate', 0):.2%} |",
            f"| Gini Coefficient (Fairness) | {sm.get('gini_coefficient', 0):.3f} |",
            f"| Worst Member Savings | ${sm.get('worst_member_savings', 0):.2f} |",
            "",
        ])
    
    lines.append("## Grid Metrics")
    lines.append("")
    
    gm = run.get("grid_metrics", {})
    if gm:
        lines.extend([
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Power Flow Convergence Rate | {gm.get('power_flow_convergence_rate', 0):.2%} |",
            f"| Voltage Violations | {gm.get('voltage_violations_count', 0)} |",
            f"| Max Voltage | {gm.get('max_voltage_pu', 1.0):.4f} pu |",
            f"| Min Voltage | {gm.get('min_voltage_pu', 1.0):.4f} pu |",
            f"| Max Line Loading | {gm.get('max_line_loading_pct', 0):.1f}% |",
            f"| Max Transformer Loading | {gm.get('max_transformer_loading_pct', 0):.1f}% |",
            "",
        ])
    
    # Add settlement info if available
    settlement = run.get("settlement")
    if settlement:
        lines.append("## Energy Sharing Settlement")
        lines.append("")
        lines.extend([
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Community Volume | {settlement.get('total_community_volume_kwh', 0):.2f} kWh |",
            f"| Community Revenue | ${settlement.get('total_community_revenue', 0):.2f} |",
            "",
        ])
    
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by Service-Aware Energy Agents Platform*")
    lines.append(f"*Generated at: {datetime.utcnow().isoformat()}*")
    
    return "\n".join(lines)


def _generate_report_json(run: dict) -> dict:
    """Generate JSON report structure."""
    return {
        "run_id": run["run_id"],
        "scenario_id": run["scenario_id"],
        "controller_type": run["controller_type"],
        "status": run["status"],
        "start_time": run["start_time"],
        "end_time": run.get("end_time"),
        "random_seed": run.get("random_seed"),
        "energy_metrics": run.get("energy_metrics", {}),
        "service_metrics": run.get("service_metrics", {}),
        "grid_metrics": run.get("grid_metrics", {}),
        "settlement": run.get("settlement"),
    }


def _markdown_to_html(markdown: str) -> str:
    """Simple markdown to HTML conversion."""
    # This is a very basic conversion - in production use a proper library
    html = markdown.replace("\n", "<br>")
    html = html.replace("# ", "<h1>").replace("## ", "<h2>").replace("### ", "<h3>")
    html = html.replace("**", "<strong>").replace("*", "<em>")
    html = html.replace("|", "<td>").replace("---", "<hr>")
    return f"<html><body>{html}</body></html>"