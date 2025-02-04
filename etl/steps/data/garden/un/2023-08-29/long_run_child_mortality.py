"""Load a meadow dataset and create a garden dataset."""
import owid.catalog.processing as pr
from owid.catalog import Dataset, Table

from etl.helpers import PathFinder, create_dataset

# Get paths and naming conventions for current step.
paths = PathFinder(__file__)


def run(dest_dir: str) -> None:
    #
    # Load inputs.
    #
    # Load meadow dataset.
    ds_igme = paths.load_dataset("igme")
    ds_gapminder_v11: Dataset = paths.load_dependency("under_five_mortality", version="2023-09-21")
    ds_gapminder_v7: Dataset = paths.load_dependency("under_five_mortality", version="2023-09-18")

    # Read table from meadow dataset.
    tb_igme = ds_igme["igme"].reset_index()

    # Select out columns of interest.
    columns = {
        "country": "country",
        "year": "year",
        "observation_value_deaths_per_1_000_live_births_under_five_mortality_rate_both_sexes_all_wealth_quintiles": "under_five_mortality",
    }
    tb_igme = tb_igme[list(columns)].rename(columns=columns, errors="raise")
    tb_igme["source"] = "igme"

    # Load full Gapminder data v11, v11 includes projections, so we need to remove years beyond the last year of IGME data

    max_year = tb_igme["year"].max()
    tb_gap_full = ds_gapminder_v11["under_five_mortality"].reset_index()
    tb_gap_full = tb_gap_full[tb_gap_full["year"] <= max_year].reset_index(drop=True)
    tb_gap_full = tb_gap_full.rename(columns={"child_mortality": "under_five_mortality"})
    tb_gap_full["source"] = "gapminder"

    # Load Gapminder data v7
    tb_gap_sel = ds_gapminder_v7["under_five_mortality_selected"].reset_index()
    tb_gap_sel["source"] = "gapminder"

    # Combine IGME and Gapminder data
    tb_combined_full = combine_datasets(tb_igme, tb_gap_full, "long_run_child_mortality")
    tb_combined_sel = combine_datasets(tb_igme, tb_gap_sel, "long_run_child_mortality_selected")

    # Calculate and estimate globally the number of children surviving their first five years
    tb_surviving = calculate_share_surviving_first_five_years(tb_combined_full)
    # Combine with full Gapminder dataset
    tb_combined_full = pr.merge(tb_combined_full, tb_surviving, on=["country", "year"], how="left")

    # Save outputs.
    tb_combined_full = tb_combined_full.drop(columns=["source"]).set_index(["country", "year"], verify_integrity=True)
    tb_combined_sel = tb_combined_sel.drop(columns=["source"]).set_index(["country", "year"], verify_integrity=True)

    #
    # Create a new garden dataset with the same metadata as the meadow dataset.
    ds_garden = create_dataset(dest_dir, tables=[tb_combined_full, tb_combined_sel], check_variables_metadata=True)
    # Save changes in the new garden dataset.
    ds_garden.save()


def combine_datasets(tb_igme: Table, tb_gap: Table, table_name: str) -> Table:
    """
    Combine IGME and Gapminder data.
    """
    tb_combined = pr.concat([tb_igme, tb_gap]).sort_values(["country", "year", "source"])
    tb_combined.metadata.short_name = table_name
    tb_combined = remove_duplicates(tb_combined, preferred_source="igme")

    return tb_combined


def remove_duplicates(tb: Table, preferred_source: str) -> Table:
    """
    Removing rows where there are overlapping years with a preference for IGME data.

    """
    assert tb["source"].str.contains(preferred_source).any()

    duplicate_rows = tb.duplicated(subset=["country", "year"], keep=False)

    tb_no_duplicates = tb[~duplicate_rows]

    tb_duplicates = tb[duplicate_rows]

    tb_duplicates_removed = tb_duplicates[tb_duplicates["source"] == preferred_source]

    tb = pr.concat([tb_no_duplicates, tb_duplicates_removed])

    assert len(tb[tb.duplicated(subset=["country", "year"], keep=False)]) == 0

    return tb


def calculate_share_surviving_first_five_years(tb_combined: Table) -> Table:
    """
    Calculate and estimate globally the number of children surviving their first five years.
    """
    # Drop out years prior to 1800 and regions that aren't countries

    tb_world = tb_combined[(tb_combined["country"] == "World")].drop(columns=["source"])

    # Add global labels and calculate the share of children surviving/dying in their first five years

    tb_world["share_dying_first_five_years"] = tb_world["under_five_mortality"] / 10
    tb_world["share_surviving_first_five_years"] = 100 - (tb_world["under_five_mortality"] / 10)

    tb_world = tb_world.drop(columns=["under_five_mortality"])

    return tb_world
