"""Load a meadow dataset and create a garden dataset."""

import owid.catalog.processing as pr
from owid.catalog import Table

from etl.data_helpers import geo
from etl.helpers import PathFinder, create_dataset

# Get paths and naming conventions for current step.
paths = PathFinder(__file__)

# Define most recent year to extend the range of years of the dataset.
LATEST_YEAR = 2022


def run(dest_dir: str) -> None:
    #
    # Load inputs.
    #
    # Load meadow dataset.
    ds_meadow = paths.load_dataset("colonial_dates_dataset")

    # Read table from meadow dataset.
    tb = ds_meadow["colonial_dates_dataset"].reset_index()

    #
    # Process data.
    #
    tb = process_data(tb)

    tb = geo.harmonize_countries(df=tb, countries_file=paths.country_mapping_path)

    # Create regional aggregations for total_colonies
    tb = regional_aggregations(tb)

    tb = tb.set_index(["country", "year"], verify_integrity=True).sort_index()

    #
    # Save outputs.
    #
    # Create a new garden dataset with the same metadata as the meadow dataset.
    ds_garden = create_dataset(
        dest_dir, tables=[tb], check_variables_metadata=True, default_metadata=ds_meadow.metadata
    )

    # Save changes in the new garden dataset.
    ds_garden.save()


def process_data(tb: Table) -> Table:
    """Process data and create new columns."""

    # Capitalize colonizer column and replace Britain by United Kingdom
    tb["colonizer"] = tb["colonizer"].str.capitalize().replace("Britain", "United Kingdom")

    # Create two tables, one for colonized countries and one for colonizers/not colonized countries
    tb_colonized = tb[tb["col"] == "1"].reset_index(drop=True)
    tb_rest = tb[tb["col"] == "0"].reset_index(drop=True)

    # Get list of colonized countries and another list of colonizers
    colonized_list = tb_colonized["country"].unique().tolist()
    colonizers_list = tb_colonized["colonizer"].unique().tolist()

    # Filter tb_rest to only include countries that are not in colonized_list or colonizers_list
    tb_rest = tb_rest[~tb_rest["country"].isin(colonized_list + colonizers_list)].reset_index(drop=True)

    # Remove duplicates for tb_rest
    tb_rest = tb_rest.drop_duplicates(subset=["country"], keep="first").reset_index(drop=True)

    # Drop colonizer column from tb_rest
    tb_rest = tb_rest.drop(columns=["colonizer"])

    # For these countries, assign the minimum year of colstart_max as colstart_max and the maximum year of colend_max as colend_max
    tb_rest["colstart_max"] = tb_colonized["colstart_max"].min()
    tb_rest["colend_max"] = LATEST_YEAR

    # Create a year column with one value per row representing the range between colstart_max and colend_max
    # NOTE: I have decided to use last date aggregations, but we could also use mean aggregations
    tb_colonized["year"] = tb_colonized.apply(lambda x: list(range(x["colstart_max"], x["colend_max"] + 1)), axis=1)
    tb_rest["year"] = tb_rest.apply(lambda x: list(range(x["colstart_max"], x["colend_max"] + 1)), axis=1)

    # Explode the year column
    tb_colonized = tb_colonized.explode("year").reset_index(drop=True)
    tb_rest = tb_rest.explode("year").reset_index(drop=True)

    # Drop colstart, colend and col columns
    tb_colonized = tb_colonized.drop(columns=["colstart_max", "colend_max", "colstart_mean", "colend_mean", "col"])
    tb_rest = tb_rest.drop(columns=["colstart_max", "colend_max", "colstart_mean", "colend_mean", "col"])

    # Create another table with the total number of colonies per colonizer and year
    tb_count = tb_colonized.groupby(["colonizer", "year"]).agg({"country": "count"}).reset_index().copy_metadata(tb)

    # Rename columns
    tb_count = tb_count.rename(columns={"colonizer": "country", "country": "total_colonies"})

    # Consolidate results in country and year columns, by merging colonizer column in each row
    tb_colonized = (
        tb_colonized.groupby(["country", "year"])
        .agg({"colonizer": lambda x: " - ".join(x)})
        .reset_index()
        .copy_metadata(tb)
    )

    # Concatenate tb_colonized and tb_rest
    tb = pr.concat([tb_colonized, tb_rest, tb_count], short_name="colonial_dates_dataset")

    # Fill years in the range (tb_colonized['year'].min(), LATEST_YEAR) not present for each country
    tb = tb.set_index(["country", "year"]).unstack().stack(dropna=False).reset_index()

    # Create an additional summarized colonizer column, replacing the values with " - " with "More than one colonizer"
    # I add the "z." to have this at the last position of the map brackets
    tb["colonizer_grouped"] = tb["colonizer"].apply(
        lambda x: "z. Multiple colonizers" if isinstance(x, str) and " - " in x else x
    )

    # Create years_colonized: counts for each year the number of years a country has been colonized (e.g. there has been a non null colonizer)
    tb["years_colonized"] = tb.groupby(["country"])["colonizer"].transform(lambda x: x.notnull().cumsum())

    # Create last_colonizer column, which is the most recent non-null colonizer for each country and year
    tb["last_colonizer"] = tb.groupby(["country"])["colonizer"].fillna(method="ffill")
    tb["last_colonizer_grouped"] = tb.groupby(["country"])["colonizer_grouped"].fillna(method="ffill")

    # For countries in colonizers_list, assign the value "Colonizer" to colonizer, colonizer_grouped, last_colonizer and last_colonizer_group column
    for col in ["colonizer", "colonizer_grouped", "last_colonizer", "last_colonizer_grouped"]:
        tb[f"{col}"] = tb[f"{col}"].where(~tb["country"].isin(colonizers_list), "zz. Colonizer")
        tb[f"{col}"] = tb[f"{col}"].where(tb["country"].isin(colonized_list + colonizers_list), "zzz. Not colonized")
        tb[f"{col}"] = tb[f"{col}"].where(~tb[f"{col}"].isnull(), "zzz. Not colonized")

    # For countries in colonizers_list total_colonies, assign 0 when it is null
    tb["total_colonies"] = tb["total_colonies"].where(
        ~((tb["country"].isin(colonizers_list)) & (tb["total_colonies"].isnull())), 0
    )

    # Add rows for the country "World" with the total number of colonies per year
    tb_count_world = tb.groupby(["year"]).agg({"total_colonies": "sum"}).reset_index()
    tb_count_world["country"] = "World"
    tb = pr.concat([tb, tb_count_world], short_name="colonial_dates_dataset")

    return tb


def regional_aggregations(tb: Table) -> Table:
    """Create regional aggregations for total_colonies."""
    # Copy table
    tb_regions = tb.copy()

    # Define non-colonies identifiers for `colonizer`
    non_colonies = ["zz. Colonizer", "zzz. Not colonized"]

    # Define colony, which is 1 if countries are not in non_colonies
    tb_regions["colony"] = tb_regions["colonizer"].apply(lambda x: 0 if x in non_colonies else 1)

    # Define regions to aggregate
    regions = [
        "Europe",
        "Asia",
        "North America",
        "South America",
        "Africa",
        "Oceania",
        "High-income countries",
        "Low-income countries",
        "Lower-middle-income countries",
        "Upper-middle-income countries",
        "European Union (27)",
        "World",
    ]

    # Add regional aggregates, by summing up the variables in `aggregations`
    for region in regions:
        tb_regions = geo.add_region_aggregates(
            tb_regions, region=region, aggregations={"colony": "sum"}, countries_that_must_have_data=[]
        )

    # Rename colony column to total_colonies
    tb_regions = tb_regions.rename(columns={"colony": "total_colonies_by_region"})

    # Select only regions in tb_regions and "World" tb_world
    tb_world = tb_regions[tb_regions["country"] == "World"].reset_index(drop=True)
    tb_regions = tb_regions[(tb_regions["country"].isin(regions)) & (tb_regions["country"] != "World")].reset_index(
        drop=True
    )

    # Concatenate and merge
    tb = pr.merge(tb, tb_world[["country", "year", "total_colonies_by_region"]], on=["country", "year"], how="left")
    tb = pr.concat([tb, tb_regions], short_name="colonial_dates_dataset")

    # Make total_colonies_by_region integer
    tb["total_colonies_by_region"] = tb["total_colonies_by_region"].astype("Int64")

    return tb
