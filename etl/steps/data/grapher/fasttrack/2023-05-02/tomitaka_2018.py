from etl.helpers import PathFinder, create_dataset
from etl.snapshot import Snapshot

paths = PathFinder(__file__)


def run(dest_dir: str) -> None:
    # load snapshot
    snap = Snapshot("fasttrack/2023-05-02/tomitaka_2018.csv")

    # load data
    tb = snap.read_csv()

    # add table, update metadata from *.meta.yml and save
    ds = create_dataset(dest_dir, tables=[tb.set_index(["country", "year"])], default_metadata=snap.metadata)
    ds.save()
