# -*- coding: utf-8 -*-
"""Generate an initial Grafana dashboard for the population simulation.

This script uses ``grafanalib`` to produce a ``sim.json`` file that can be
imported into Grafana. The dashboard contains two panels querying data from the
``simulation_results`` table in PostgreSQL.

Usage::

    python grafana/initial_dashboard.py [--output PATH] [--overwrite]

To import ``sim.json`` in Grafana:
  1. Open the Grafana UI and choose ``Dashboards -> Import``.
  2. Upload the generated JSON file or paste its contents.
  3. When asked for a data source, select the PostgreSQL source configured for
     your simulation data (defaults to ``SimulationDB``).

"""

from __future__ import annotations

import argparse
import json
import os

from grafanalib.core import Dashboard, Graph, SqlTarget
from grafanalib._gen import DashboardEncoder

DEFAULT_OUTPUT = os.path.join("grafana", "dashboards", "sim.json")
DEFAULT_DATASOURCE = "SimulationDB"


def create_dashboard(datasource: str = DEFAULT_DATASOURCE) -> Dashboard:
    """Construct a dashboard with population and births panels."""

    population_panel = Graph(
        title="Population over time",
        dataSource=datasource,
        targets=[
            SqlTarget(
                refId="A",
                rawSql=(
                    "SELECT\n"
                    "  $__time(time) as time,\n"
                    "  population\n"
                    "FROM simulation_results\n"
                    "WHERE $__timeFilter(time)\n"
                    "ORDER BY time"
                ),
                format="time_series",
            )
        ],
    )

    births_panel = Graph(
        title="Births over time",
        dataSource=datasource,
        targets=[
            SqlTarget(
                refId="A",
                rawSql=(
                    "SELECT\n"
                    "  $__time(time) as time,\n"
                    "  births\n"
                    "FROM simulation_results\n"
                    "WHERE $__timeFilter(time)\n"
                    "ORDER BY time"
                ),
                format="time_series",
            )
        ],
    )

    return Dashboard(
        title="Simulation Results",
        uid="bptk-sim-results",
        panels=[population_panel, births_panel],
    )


def save_dashboard(dashboard: Dashboard, path: str, overwrite: bool = False) -> None:
    """Write dashboard JSON to ``path``.

    If ``overwrite`` is ``False`` and the file exists, an exception is raised to
    avoid clobbering existing dashboards.
    """
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(
            f"Dashboard {path} already exists. Use --overwrite to replace it."
        )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(dashboard.to_json_data(), fh, indent=2, sort_keys=True, cls=DashboardEncoder)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Grafana dashboard JSON")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path of JSON to write")
    parser.add_argument(
        "--datasource",
        default=DEFAULT_DATASOURCE,
        help="Name of the Grafana PostgreSQL data source",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing dashboard JSON file",
    )
    args = parser.parse_args()

    dashboard = create_dashboard(args.datasource)
    save_dashboard(dashboard, args.output, overwrite=args.overwrite)
    print(f"Dashboard written to {args.output}")


if __name__ == "__main__":
    main()
