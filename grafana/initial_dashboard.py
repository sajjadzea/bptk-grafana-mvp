from grafanalib.core import Dashboard, Graph, Target

dashboard = Dashboard(
  title="Simulation Results",
  panels=[
    Graph(
      title="Stock over time",
      dataSource='SimulationDB',
      targets=[Target(refId="A",)**...**])
  ]
)
dashboard.save('grafana/dashboards/sim.json')
