"""Multi-format export for scraped business data."""

import os

import pandas as pd

from google_maps.models import BusinessList


SUPPORTED_FORMATS = {"csv", "xlsx", "json", "all"}


def export(
    results: BusinessList,
    directory: str,
    name: str,
    fmt: str = "all",
) -> list[str]:
    """Save a BusinessList to disk in the requested format(s).

    Returns a list of file paths that were written.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{fmt}', use one of {SUPPORTED_FORMATS}")

    if not results:
        return []

    os.makedirs(directory, exist_ok=True)
    df = pd.DataFrame([b.to_dict() for b in results.businesses])
    paths: list[str] = []

    if fmt in ("csv", "all"):
        p = os.path.join(directory, f"{name}.csv")
        df.to_csv(p, index=False)
        paths.append(p)

    if fmt in ("xlsx", "all"):
        p = os.path.join(directory, f"{name}.xlsx")
        df.to_excel(p, index=False)
        paths.append(p)

    if fmt in ("json", "all"):
        p = os.path.join(directory, f"{name}.json")
        df.to_json(p, orient="records", indent=2)
        paths.append(p)

    return paths
