import pandas as pd
from owid import catalog

from etl.helpers import PathFinder, create_dataset
from etl.snapshot import Snapshot

P = PathFinder(__file__)


def run(dest_dir: str) -> None:
    # load snapshot
    snap = Snapshot("fasttrack/2023-08-07/pain_hours_days_hen_systems.csv")

    # load data
    data = pd.read_csv(snap.path)

    # create empty dataframe and table
    tb = catalog.Table(data, short_name=P.short_name)

    # add table, update metadata from *.meta.yml and save
    ds = create_dataset(dest_dir, tables=[tb], default_metadata=snap.metadata)
    ds.save()
