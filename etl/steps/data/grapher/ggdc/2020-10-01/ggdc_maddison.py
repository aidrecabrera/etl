from owid import catalog

from etl.helpers import Names

N = Names(__file__)


def run(dest_dir: str) -> None:
    dataset = catalog.Dataset.create_empty(dest_dir, N.garden_dataset.metadata)
    dataset.save()

    table = N.garden_dataset["maddison_gdp"].reset_index()

    dataset.add(table[["country", "year", "gdp", "gdp_per_capita", "population"]])