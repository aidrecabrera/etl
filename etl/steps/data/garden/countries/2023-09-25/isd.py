"""Load a meadow dataset and create a garden dataset."""

import owid.catalog.processing as pr
from owid.catalog import Table
from structlog import get_logger

from etl.data_helpers import geo
from etl.helpers import PathFinder, create_dataset

from .shared import (
    add_latest_years_with_constat_num_countries,
    init_table_countries_in_region,
)

# Get paths and naming conventions for current step.
paths = PathFinder(__file__)
# Only for table tb_regions:
# The current list of members goes until 2016, we artificially extend it until year of latest 31st of December
EXPECTED_LAST_YEAR = 2016
# Logger
log = get_logger()


def run(dest_dir: str) -> None:
    #
    # Load inputs.
    #
    # Load meadow dataset.
    ds_meadow = paths.load_dataset("isd")

    # Read table from meadow dataset.
    tb = ds_meadow["isd"].reset_index()

    #
    # Process data.
    #
    log.info("isd: harmonizing countries")
    tb = geo.harmonize_countries(
        df=tb,
        countries_file=paths.country_mapping_path,
        country_col="statename",
    )

    # Fixes
    log.info("isd: fixing data")
    tb = fix_data(tb)

    # Create new table
    log.info("isd: creating table with countries in region")
    tb_regions = create_table_countries_in_region(tb=tb)

    # Add to tables list
    tables = [
        tb.set_index(["cownum", "start", "end"], verify_integrity=True).sort_index(),
        tb_regions.set_index(["region", "year"], verify_integrity=True).sort_index(),
    ]

    # tb = tb.set_index(["country", "year"], verify_integrity=True)

    #
    # Save outputs.
    #
    # Create a new garden dataset with the same metadata as the meadow dataset.
    ds_garden = create_dataset(
        dest_dir, tables=tables, check_variables_metadata=True, default_metadata=ds_meadow.metadata
    )

    # Save changes in the new garden dataset.
    ds_garden.save()


def fix_data(tb: Table) -> Table:
    """Fix ISD data.

    Original ISD data has some issues:

        - Wrong date (31st of September)
        - Some cownums are mapped to more than one country.

    NOTE: This has been reported to the source
    """
    # Fixes wrong date '31-09-1896' -> '30-09-1896' (there is no 31st Sep)
    # I've reported this to the source
    tb["end"] = tb["end"].astype(str)
    tb.loc[tb["end"] == "31-09-1896", "end"] = "30-09-1896"

    # Fix COW Num
    ## 7589 is mapped to "Bharatpur" and "Chamba"
    ## 7590 is mapped to "Cutch" and "Singhbhum"
    ## 8542 is mapped to "Karangasem" and "Mataram Lombok"
    ## Checking the docs of v1 (v2 does not provide IDs): https://static1.squarespace.com/static/54eccfa0e4b08d8eee5174af/t/54ede030e4b0a0f14faa8f84/1424875568381/ISD+Codebook_version1.pdf, it seems that the correct mapping is:
    ## Bharatpur →  7589 (already good)
    ## Chamba → 7590
    tb.loc[(tb["cownum"] == 7589) & (tb["cowid"] == "CHM"), "cownum"] = 7590
    ## Cutch → 7591
    tb.loc[(tb["cownum"] == 7590) & (tb["cowid"] == "CUT"), "cownum"] = 7591
    ## Singhbhum → ? (new id, not in v1 doc)
    tb.loc[(tb["cownum"] == 7590) & (tb["cowid"] == "SNB"), "cownum"] = 75911
    ## Karangasem → 8542 (already good)
    ## Mataram Lombok → ? (new id, not in v1 doc)
    tb.loc[(tb["cownum"] == 8542) & (tb["cowid"] == "LOM"), "cownum"] = 85421

    return tb


def create_table_countries_in_region(tb: Table) -> Table:
    """Create table with number of countries in each region per year."""
    tb = init_table_countries_in_region(
        tb,
        date_format="%d-%m-%Y",
        column_start="start",
        column_end="end",
        column_id="cownum",
        column_country="statename",
    )

    # Get region name, then obtain number of countries per region per year
    tb["region"] = tb["cownum"].apply(code_to_region)
    # Get number of countries per region per year
    tb_regions = (
        tb.groupby(["region", "year"], as_index=False)
        .agg({"cownum": "nunique"})
        .rename(columns={"cownum": "number_countries"})
    )

    # The code below is commented (and not deleted) in case we wanted to use it in the future
    # It tries to add other regions to the table (possible overlapping with the existing ones)
    # The code should be checked again, as it might be outdated and not work
    #
    # Same as before, but with an alternate region set. Basically, instead of (Africa, Middle East) -> (Sub-Saharan Africa, North Africa & Middle East)
    # tb["region_alt"] = tb["cownum"].apply(code_to_region_alt)
    # tb_regions_alt = (
    #     tb.groupby(["region_alt", "year"], as_index=False)
    #     .agg({"cownum": "nunique"})
    #     .rename(columns={"cownum": "number_countries"})
    # ).rename(columns={"region_alt": "region"})
    # tb_regions = pr.concat([tb_regions, tb_regions_alt], ignore_index=True)

    # Get numbers for World
    tb_world = (
        tb.groupby(["year"], as_index=False).agg({"cownum": "nunique"}).rename(columns={"cownum": "number_countries"})
    )
    tb_world["region"] = "World"

    # Combine
    tb_regions = pr.concat([tb_regions, tb_world], ignore_index=True, short_name="isd_regions")

    # Finish by adding missing last years
    tb_regions = add_latest_years_with_constat_num_countries(
        tb_regions,
        column_year="year",
        expected_last_year=EXPECTED_LAST_YEAR,
    )

    return tb_regions


def code_to_region(cow_code: int) -> str:
    """Convert code to region name."""
    match cow_code:
        case c if 2 <= c <= 165:
            return "Americas"
        case c if (200 <= c <= 395) or (c in [2558, 3375]):
            return "Europe"
        case c if (402 <= c <= 626) or (4044 <= c <= 6257):
            return "Africa"
        case c if (630 <= c <= 698) or (6821 <= c <= 6845):
            return "Middle East"
        case c if (700 <= c <= 990) or (7003 <= c <= 9210) or (c in [75911, 85421]):
            return "Asia and Oceania"
        case _:
            raise ValueError(f"Invalid ISD code: {cow_code}")


def code_to_region_alt(cow_code: int) -> str:
    """Convert code to (alternative) region name.

    Adds regions that might overlap with the existing ones.
    """
    match cow_code:
        case c if (630 <= c <= 698) or (6821 <= c <= 6845):
            return "North Africa and the Middle East"
        case c if (700 <= c <= 990) or (7003 <= c <= 9210) or (c in [75911, 85421]):
            return "Asia and Oceania"
        case _:
            return "Rest"