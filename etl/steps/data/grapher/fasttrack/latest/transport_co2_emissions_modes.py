import pandas as pd
from owid import catalog

from etl.helpers import PathFinder, create_dataset
from etl.snapshot import Snapshot

paths = PathFinder(__file__)


def run(dest_dir: str) -> None:
    # load snapshot
    snap = Snapshot("fasttrack/latest/transport_co2_emissions_modes.csv")

    # load data
    data = pd.read_csv(snap.path)

    # create empty dataframe and table
    tb = catalog.Table(data, short_name=paths.short_name)

    # add table, update metadata from *.meta.yml and save
    ds = create_dataset(dest_dir, tables=[tb.set_index(["country", "year"])], default_metadata=snap.metadata)
    ds.save()
