from gbd_tools import run_wrapper
from structlog import get_logger

from etl.helpers import PathFinder

# naming conventions
paths = PathFinder(__file__)
log = get_logger()


def run(dest_dir: str) -> None:
    # Name the dimensions we are keeping and pivoting by - this varies for gbd_risk
    dims = ["sex", "age", "cause"]

    # Get dataset level variables

    dataset = paths.short_name
    log.info(f"{dataset}.start")
    country_mapping_path = paths.directory / "gbd.countries.json"
    excluded_countries_path = paths.directory / "gbd.excluded_countries.json"

    # Run the function to produce garden dataset
    run_wrapper(dataset, country_mapping_path, excluded_countries_path, dest_dir, dims)
    log.info(f"{dataset}.end")
