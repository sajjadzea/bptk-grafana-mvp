
#                                                       /`-
# _                                  _   _             /####`-
# | |                                | | (_)           /########`-
# | |_ _ __ __ _ _ __  ___  ___ _ __ | |_ _ ___       /###########`-
# | __| '__/ _` | '_ \/ __|/ _ \ '_ \| __| / __|   ____ -###########/
# | |_| | | (_| | | | \__ \  __/ | | | |_| \__ \  |    | `-#######/
# \__|_|  \__,_|_| |_|___/\___|_| |_|\__|_|___/  |____|    `- # /
#
# Copyright (c) 2021 transentis labs GmbH
# MIT License


import pandas as pd

from ..logger import log
from .scenario_runner import ScenarioRunner
from ..sdsimulation import SdSimulation


class SdRunner(ScenarioRunner):
    """Runs pure SD scenarios created with XMILE or with SD DSL.

    This is the class that merges the scenario settings (which it reads from SdScenario) onto the actual simulation model (which is either a Model or a SimulationModel).

    Runs a set of scenarios for a given scenario manager.
    """

    # Scenarios comes as scenario object dict, equations as a dict: { equation : [scenario1,scenario2...]}
    def __generate_df(self, sd_results_dict, return_format, scenarios, equations):
        """
        Generates a dataFrame from simulation results. Generate series names and time series
        :param sd_results_dict: a dictionary that contains the latest updated values of the simulation results in a dictionary format
        :param return_format: the data type of the return.(can either be dataframe, dictionary or json)
        :param scenarios: names of scenarios
        :param equations:  names of equations
        :param start_date: start date of the timeseries
        :param freq: frequency of time series, e.g. "D" for daily data
        :param series_names: names of series to rename to, using a dict: {equation_name : rename_to}
        :return:
        """
        
        ## Generate empty df to plot
        plot_df = pd.DataFrame()


        for scenario in scenarios.keys():
            df = scenarios[scenario].result

            if not df is None:
                for equation in equations.keys():

                    if equation in df.columns:
                        series = df[equation]
            
                        if scenarios[scenario].scenario_manager not in sd_results_dict:
                            sd_results_dict[scenarios[scenario].scenario_manager]=dict()
                        
                        if scenarios[scenario].name not in sd_results_dict[scenarios[scenario].scenario_manager]:
                            sd_results_dict[scenarios[scenario].scenario_manager][scenarios[scenario].name]=dict()
                            
                        if "equations" not in sd_results_dict[scenarios[scenario].scenario_manager][scenarios[scenario].name]:
                            sd_results_dict[scenarios[scenario].scenario_manager][scenarios[scenario].name]["equations"]=dict()
                            
                        if equation not in sd_results_dict[scenarios[scenario].scenario_manager][scenarios[scenario].name]["equations"]:
                            if return_format == "json":
                                sd_results_dict[scenarios[scenario].scenario_manager][scenarios[scenario].name]["equations"][equation]= df[equation].to_dict()
                            else:
                                sd_results_dict[scenarios[scenario].scenario_manager][scenarios[scenario].name]["equations"][equation]= df[equation]
                                
                            
                        series.name = scenarios[scenario].scenario_manager + "_" + scenarios[scenario].name + "_" + equation
                        plot_df[series.name] = series
            
            simulation_results=[]
            if return_format=="dict" or return_format=="json":
                simulation_results=sd_results_dict
            elif return_format=="df":
                simulation_results=plot_df
           
        return simulation_results


    def run_scenario_step(self, step, settings, scenario_manager, scenarios, equations):
        """
        Run a step of the given scenarios and return data for the given equations and agents
        """    

        log("[INFO] Attempting to load scenarios from scenarios folder.")
        scenario_objects = self.scenario_manager_factory.get_scenarios(scenario_managers=[scenario_manager],
                                                                       scenarios=scenarios, scenario_manager_type="sd")

        #### Run the simulation scenarios

        if len(scenario_objects) == 0 :
            log("[ERROR] No scenarios found for scenario manager \"{}\" and scenarios \"{}\"".format(scenario_manager,",".join(scenarios)))

        for scenario, sc in scenario_objects.items():

            if sc.sd_simulation is None:
                # need to set up the sd simulation
                # TODO: the following should really be part of SdSimulation
                sc.sd_simulation = SdSimulation(model=sc.model, name=sc.name)
                # first apply the scenario settings
                for name, value in sc.constants.items():
                    sc.sd_simulation.change_equation(name=name, value=value)
                for name, points in sc.points.items():
                    sc.sd_simulation.change_points(name=name, value=points)
                sc.sd_simulation.change_runspecs(starttime=sc.starttime,stoptime=sc.stoptime,dt=sc.dt)

            # now the settings relevant for this step
            
            if settings:
                if scenario_manager in settings:
                    if scenario in settings[scenario_manager]:
                        if "constants" in settings[scenario_manager][scenario]:
                            constants = settings[scenario_manager][scenario]["constants"]
                            for name, value in constants.items():
                                sc.sd_simulation.change_equation(name=name, value=value)
                        if "points" in settings[scenario_manager][scenario]:        
                            points = settings[scenario_manager][scenario]["points"] 
                            for name, points in points.items():
                                sc.sd_simulation.change_points(name=name, value=points)

            sc.result = sc.sd_simulation.start(output=["frame"], start=step, until=step,equations=equations)

        return {name:scenario.result.to_dict() for name,scenario in scenario_objects.items()}

    #TODO this really should just take on scenario manager - it doesn't make sense to call it on multiple scenario managers. It should be called run_scenarios
    def run_scenario(self, sd_results_dict, return_format, scenarios, equations, scenario_managers=[]):
        """
        Runs all relevant scenarios for a given scenario manager.

        :param sd_results_dict: a dictionary that contains the latest updated values of the simulation results in a dictionary format
        :param return_format: the data type of the return.(can either be dataframe, dictionary or json).
        :param scenarios: names of scenarios to plot
        :param equations:  names of equations to plot
        :param scenario_managers: names of scenario managers to plot
       """

        # Obtain simulation results
        scenario_objects = self._run_scenarios(scenarios=scenarios, equations=equations, output=["frame"], scenario_managers=scenario_managers)

        if len(scenario_objects.keys()) == 0:
            log("[ERROR] No scenario found for scenario_managers={} and scenario_names={}. Cancelling".format(
                str(scenario_managers), str(scenarios)))
            return None

        # Visualize Object
        dict_equations = {}

        # Clean up scenarios if we did not find all with the specified scenario managers. Will not warn if a scenario name is missing
        scenarios = [key for key in scenario_objects.keys()]

        all_equations = [item for sublist in [list(mod.model.equations.keys()) for mod in scenario_objects.values()] for item in sublist]
        all_equations = list(dict.fromkeys(all_equations))
        # Generate an index {equation .: [scenario1,scenario2...], equation2: [...] }
        # We are checking which scenarios can handle which equation
        import re
        for scenario_name in scenarios:
            sc = scenario_objects[scenario_name]  # <-- Obtain the actual scenario object
            for equation in equations:

                # Looking for patterns that refer to an arrayed variable. "*"-Equations are not really equations for us. Hence, removing array notation to find the raw name of the equation
                if "*" in equation:
                    re_find_indices = r'\[([^)]+)\]'
                    search = re.search(re_find_indices, equation)  # .group(0)#.replace("[", "").replace("]", "")
                    if search:
                        group = search.group(0)
                        cleaned_equation =equation.replace(group, "")
                    else: cleaned_equation = equation

                else: # Not an array variable
                    cleaned_equation = equation
                if cleaned_equation not in dict_equations.keys(): dict_equations[equation] = []

                if cleaned_equation in sc.model.equations.keys():
                    dict_equations[equation] += [scenario_name]

        # Search whether we found a match for all equations. Otherwise "did you mean" support
        for equation,scenario in dict_equations.items():
            if scenario == []:
                from ..util.didyoumean import didyoumean
                nearest_equations = didyoumean(equation, all_equations, 3)

                if len(nearest_equations) > 0:log("[ERROR] No simulation model containing equation \"{}\". Did you maybe mean one of \"{}\"?".format(equation,", ".join(nearest_equations)))
                else: log("[ERROR] No simulation model containing equation \"{}\"".format(equation))
        return self.__generate_df(sd_results_dict, return_format, scenario_objects, dict_equations,
                                )

    def _run_scenarios(self, scenarios, equations=[], output=["frame"], scenario_managers=[]):
        """
        Method to run the simulations
        :param scenarios: names of scenarios to simulate
        :param equations: equations to simulate
        :param output: output type, default as a dataFrame
        :param scenario_managers: scenario managers as a list of names of scenario managers
        :return: dict of SimulationScenario
        """
        ## Load scenarios

        log("[INFO] Attempting to load scenarios from scenarios folder.")
        scenario_objects = self.scenario_manager_factory.get_scenarios(scenario_managers=scenario_managers,
                                                                       scenarios=scenarios, scenario_manager_type="sd")

        #### Run the simulation scenarios

        if len(scenario_objects) == 0 :
            log("[ERROR] No scenarios found for scenario managers \"{}\" and scenarios \"{}\"".format(",".join(scenario_managers),",".join(scenarios)))

        for key in scenario_objects.keys():
            if key in scenarios:
                sc = scenario_objects[key]
                simu = SdSimulation(model=sc.model, name=sc.name)
                for const in sc.constants.keys():
                    simu.change_equation(name=const, value=sc.constants[const])
                for name, points in sc.points.items():
                    simu.change_points(name=name, value=points)
                simu.change_runspecs(starttime=sc.starttime,stoptime=sc.stoptime,dt=sc.dt)

                sc.result = simu.start(output=output, equations=equations)

        return scenario_objects

