"""Load a meadow dataset and create a garden dataset."""

import pandas as pd
from owid.catalog import Dataset, Table
from structlog import get_logger

from etl.helpers import PathFinder, create_dataset

log = get_logger()

# Get paths and naming conventions for current step.
paths = PathFinder(__file__)

# Unit conversion factor to change from bushels per acre to tonnes per hectare.
BUSHELS_PER_ACRE_TO_TONNES_PER_HECTARE = 0.06725


def run(dest_dir: str) -> None:
    log.info("us_corn_yields.start")

    #
    # Load inputs.
    #
    # Load meadow dataset.
    ds_meadow: Dataset = paths.load_dependency("us_corn_yields")

    # Read table from meadow dataset.
    tb_meadow = ds_meadow["us_corn_yields"]

    # Create a dataframe with data from the table.
    df = pd.DataFrame(tb_meadow)

    #
    # Process data.
    #
    # Change units of corn yield.
    df["corn_yield"] *= BUSHELS_PER_ACRE_TO_TONNES_PER_HECTARE

    # Create a new table with the processed data.
    tb_garden = Table(df, like=tb_meadow)

    #
    # Save outputs.
    #
    # Create a new garden dataset with the same metadata as the meadow dataset.
    ds_garden = create_dataset(dest_dir, tables=[tb_garden], default_metadata=ds_meadow.metadata)

    # Save changes in the new garden dataset.
    ds_garden.save()

    log.info("us_corn_yields.end")
