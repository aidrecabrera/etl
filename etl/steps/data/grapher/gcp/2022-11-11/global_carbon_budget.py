from owid import catalog

from etl.helpers import Names

# For two stacked area charts (namely "CO₂ emissions by fuel type" and "Cumulative CO₂ emissions by source") having
# nans in the data causes the chart to show only years where all sources have data.
# To avoid this, create additional variables that have nans filled with zeros.
VARIABLES_TO_FILL_WITH_ZEROS = [
    'emissions_total',
    'emissions_from_cement',
    'emissions_from_coal',
    'emissions_from_flaring',
    'emissions_from_gas',
    'emissions_from_land_use_change',
    'emissions_from_oil',
    'emissions_from_other_industry',
    'cumulative_emissions_total',
    'cumulative_emissions_from_cement',
    'cumulative_emissions_from_coal',
    'cumulative_emissions_from_flaring',
    'cumulative_emissions_from_gas',
    'cumulative_emissions_from_land_use_change',
    'cumulative_emissions_from_oil',
    'cumulative_emissions_from_other_industry',
]

N = Names(__file__)


def run(dest_dir: str) -> None:
    # Create a new Grapher dataset.
    dataset = catalog.Dataset.create_empty(dest_dir, N.garden_dataset.metadata)

    # Load table from Garden dataset.
    table = N.garden_dataset["global_carbon_budget"]

    ####################################################################################################################
    # TODO: Uncomment this once these variables have been removed from the garden step.
    # # Create additional variables in the table that have nans filled with zeros (for two specific stacked area charts).
    # for variable in VARIABLES_TO_FILL_WITH_ZEROS:
    #     new_variable_name = variable + "_zero_filled"
    #     table[new_variable_name] = table[variable].fillna(0)
    #     table[new_variable_name].metadata = deepcopy(table[variable].metadata)
    #     table[new_variable_name].metadata.title = table[variable].metadata.title + " (zero filled)"
    #     table[new_variable_name].metadata.description =\
    #         table[variable].metadata.description + " Missing data has been filled by zero."
    ####################################################################################################################

    # Add table to Grapher dataset and save dataset.
    dataset.add(table)
    dataset.save()
