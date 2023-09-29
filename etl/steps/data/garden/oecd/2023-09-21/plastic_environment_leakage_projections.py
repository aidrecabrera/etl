"""Load a meadow dataset and create a garden dataset."""

from etl.helpers import PathFinder, create_dataset

# Get paths and naming conventions for current step.
paths = PathFinder(__file__)


def run(dest_dir: str) -> None:
    #
    # Load inputs.
    #
    # Load meadow datasets for global plastic emissions by gas, application type and polymer and read tables.
    ds_meadow = paths.load_dataset("plastic_environment_leakage_projections")
    tb = ds_meadow["plastic_environment_leakage_projections"]
    #
    # Process data.
    #
    # Convert million to actual number
    tb["value"] = tb["value"] * 1e6
    #
    # Save outputs.
    #
    # Create a new garden dataset with the same metadata as the meadow dataset.
    ds_garden = create_dataset(
        dest_dir,
        tables=[tb],
        check_variables_metadata=True,
        default_metadata=ds_meadow.metadata,
    )

    # Save changes in the new garden dataset.
    ds_garden.save()
