"""Multi-format export for SERP data."""

import json
import os

import pandas as pd

from google_search.models import SerpResultSet


SUPPORTED_FORMATS = {"csv", "xlsx", "json", "all"}


def export_organic(
    results: SerpResultSet,
    directory: str,
    name: str,
    fmt: str = "all",
) -> list[str]:
    """Export organic results to disk in the requested format(s).

    Returns a list of file paths written.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{fmt}', use one of {SUPPORTED_FORMATS}")

    organic = results.all_organic()
    if not organic:
        return []

    os.makedirs(directory, exist_ok=True)

    rows = []
    for r in organic:
        row = {
            "position": r.position,
            "title": r.title,
            "url": r.url,
            "displayed_url": r.displayed_url,
            "description": r.description,
            "date": r.date,
            "sitelinks_count": len(r.sitelinks),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    paths: list[str] = []

    if fmt in ("csv", "all"):
        p = os.path.join(directory, f"{name}_organic.csv")
        df.to_csv(p, index=False)
        paths.append(p)

    if fmt in ("xlsx", "all"):
        p = os.path.join(directory, f"{name}_organic.xlsx")
        df.to_excel(p, index=False)
        paths.append(p)

    if fmt in ("json", "all"):
        p = os.path.join(directory, f"{name}_organic.json")
        df.to_json(p, orient="records", indent=2)
        paths.append(p)

    return paths


def export_full(
    results: SerpResultSet,
    directory: str,
    name: str,
    fmt: str = "all",
) -> list[str]:
    """Export all SERP features to disk.

    For XLSX: each feature type gets its own sheet.
    For JSON: all features in one structured file.
    For CSV: organic results only (other features are nested structures).

    Returns a list of file paths written.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{fmt}', use one of {SUPPORTED_FORMATS}")

    if not results:
        return []

    os.makedirs(directory, exist_ok=True)
    paths: list[str] = []

    # Always export organic results as flat files
    paths.extend(export_organic(results, directory, name, fmt))

    # Full structured export (JSON)
    if fmt in ("json", "all"):
        full_data = []
        for page in results.pages:
            full_data.append(page.to_dict())

        p = os.path.join(directory, f"{name}_full.json")
        with open(p, "w") as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
        paths.append(p)

    # XLSX with separate sheets per feature
    if fmt in ("xlsx", "all"):
        p = os.path.join(directory, f"{name}_full.xlsx")
        with pd.ExcelWriter(p, engine="openpyxl") as writer:
            # Organic
            organic = results.all_organic()
            if organic:
                df = pd.DataFrame([r.to_dict() for r in organic])
                df.drop(columns=["sitelinks"], inplace=True, errors="ignore")
                df.to_excel(writer, sheet_name="Organic", index=False)

            # Ads
            ads = []
            for page in results.pages:
                ads.extend(page.ads)
            if ads:
                df = pd.DataFrame([a.to_dict() for a in ads])
                df.drop(columns=["extensions"], inplace=True, errors="ignore")
                df.to_excel(writer, sheet_name="Ads", index=False)

            # PAA
            paa = []
            for page in results.pages:
                paa.extend(page.people_also_ask)
            if paa:
                df = pd.DataFrame([p.to_dict() for p in paa])
                df.to_excel(writer, sheet_name="People Also Ask", index=False)

            # Local Pack
            local = []
            for page in results.pages:
                local.extend(page.local_pack)
            if local:
                df = pd.DataFrame([lp.to_dict() for lp in local])
                df.to_excel(writer, sheet_name="Local Pack", index=False)

            # Videos
            videos = []
            for page in results.pages:
                videos.extend(page.videos)
            if videos:
                df = pd.DataFrame([v.to_dict() for v in videos])
                df.to_excel(writer, sheet_name="Videos", index=False)

            # Related Searches
            related = []
            for page in results.pages:
                related.extend(page.related_searches)
            if related:
                df = pd.DataFrame([rs.to_dict() for rs in related])
                df.to_excel(writer, sheet_name="Related Searches", index=False)

            # Summary
            summary_rows = []
            for page in results.pages:
                summary_rows.append({
                    "query": page.query,
                    "page": page.page_number + 1,
                    "total_results": page.total_results_text,
                    "search_time": page.search_time_text,
                    "organic_count": len(page.organic),
                    "ads_count": len(page.ads),
                    "has_featured_snippet": page.featured_snippet is not None,
                    "paa_count": len(page.people_also_ask),
                    "has_knowledge_panel": page.knowledge_panel is not None,
                    "local_pack_count": len(page.local_pack),
                    "video_count": len(page.videos),
                    "related_count": len(page.related_searches),
                })
            if summary_rows:
                df = pd.DataFrame(summary_rows)
                df.to_excel(writer, sheet_name="Summary", index=False)

        paths.append(p)

    return paths
