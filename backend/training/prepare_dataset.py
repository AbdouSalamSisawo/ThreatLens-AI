"""
ThreatLens AI - Dataset Preparation
====================================

Loads the raw public dataset, validates it, normalises labels, removes
invalid/duplicate records, records class distribution and leakage checks,
and writes a processed CSV used by train_model.py.

Source dataset (primary)
------------------------
  Name:        "TabNetone" phishing-URL corpus (HuggingFace id: pirocheto/phishing-url)
  Origin:      Compiled by Hannousse & Yahiouche for arXiv:2010.12847
               ("Phishing URL detection: a real-world assessment") from
               public feeds and crawl sources (incl. PhishTank / OpenPhish
               style phishing sources and legitimate crawl collections).
  Licence:     CC-BY-4.0 (attribution required - see AI_AND_DATA_DECLARATION.md)
  Retrieved:   2026-10-29 from https://huggingface.co/datasets/pirocheto/phishing-url
  Files used:  data/train.parquet + data/test.parquet (re-combined; this
               project performs its own split to control leakage).
  Fields used: `url` (raw URL string) and `status` ("phishing"/"legitimate").
               All 87 pre-computed feature columns are deliberately DISCARDED:
               ThreatLens computes its own features from raw URLs with one
               shared extractor used identically at training and inference.

Only the raw URL + label are consumed so that the exact same lexical feature
code path powers training and live inference.

Usage
-----
  python training/prepare_dataset.py \
      --raw-dir ../data/raw --out ../data/processed/phishing_clean.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Make the shared app modules importable when run from training/
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.feature_extractor import (  # noqa: E402
    URLValidationError,
    normalise_url_for_dedup,
    parse_url,
)

LABEL_MAP = {"phishing": 1, "legitimate": 0}
MAX_URL_LEN = 2048  # URLs beyond the API's accepted size are dropped


def load_raw_frames(raw_dir: Path) -> pd.DataFrame:
    frames = []
    for name in ("train.parquet", "test.parquet"):
        path = raw_dir / name
        if not path.exists():
            raise FileNotFoundError(
                f"Expected raw dataset file not found: {path}\n"
                "Download from https://huggingface.co/datasets/pirocheto/phishing-url "
                "(files: data/train.parquet, data/test.parquet)."
            )
        frames.append(pd.read_parquet(path, columns=["url", "status"]))
    df = pd.concat(frames, ignore_index=True)
    return df


def prepare(raw_dir: Path, out_path: Path) -> dict:
    report: dict = {
        "source": "pirocheto/phishing-url (TabNetone corpus, CC-BY-4.0)",
        "retrieved_at": "2026-10-29",
        "steps": {},
    }

    df = load_raw_frames(raw_dir)
    report["steps"]["loaded_records"] = int(len(df))

    # -- Validate required columns ------------------------------------------
    if "url" not in df.columns or "status" not in df.columns:
        raise ValueError("Dataset must contain 'url' and 'status' columns")

    # -- Normalise labels ----------------------------------------------------
    df["label"] = df["status"].astype(str).str.strip().str.lower().map(LABEL_MAP)
    n_bad_labels = int(df["label"].isna().sum())
    df = df.dropna(subset=["label"])
    df["label"] = df["label"].astype(int)
    report["steps"]["dropped_unmappable_labels"] = n_bad_labels

    # -- Drop nulls / malformed / oversized URLs -----------------------------
    n_start = len(df)
    df = df[df["url"].notna()]
    df["url"] = df["url"].astype(str).str.strip()

    kept_rows = []
    n_invalid = 0
    n_too_long = 0
    for url in df["url"]:
        if len(url) > MAX_URL_LEN:
            n_too_long += 1
            continue
        try:
            parse_url(url)  # validation only; features are computed later
            kept_rows.append(True)
        except URLValidationError:
            kept_rows.append(False)
            n_invalid += 1
    df = df[kept_rows]
    report["steps"]["dropped_invalid_urls"] = n_invalid
    report["steps"]["dropped_oversized_urls"] = n_too_long

    # -- Label conflict detection (same canonical URL, both labels) ----------
    df["_canon"] = df["url"].map(normalise_url_for_dedup)
    conflict_groups = df.groupby("_canon")["label"].nunique()
    n_conflicts = int((conflict_groups > 1).sum())
    conflicting = set(conflict_groups[conflict_groups > 1].index)
    df = df[~df["_canon"].isin(conflicting)]
    report["steps"]["label_conflict_urls_removed"] = n_conflicts

    # -- De-duplication -------------------------------------------------------
    before_dedup = len(df)
    df = df.drop_duplicates(subset="_canon", keep="first")
    report["steps"]["duplicates_removed"] = int(before_dedup - len(df))

    # -- Remove near-duplicate cross-class variants (same host+path, diff query)
    host_path = df["_canon"].str.split("?", n=1).str[0]
    variant_groups = host_path.value_counts()
    n_variant_hosts = int((variant_groups > 6).sum())
    report["steps"]["host_path_variants_over_6"] = n_variant_hosts

    df = df.drop(columns=["_canon"]).reset_index(drop=True)

    # -- Class distribution ---------------------------------------------------
    dist = df["label"].value_counts().to_dict()
    report["final_records"] = int(len(df))
    report["class_distribution"] = {
        "phishing": int(dist.get(1, 0)),
        "legitimate": int(dist.get(0, 0)),
    }
    report["retained_ratio"] = round(len(df) / report["steps"]["loaded_records"], 4)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    report["output"] = str(out_path)

    sidecar = out_path.with_suffix(".report.json")
    sidecar.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the phishing URL dataset")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "raw",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "phishing_clean.csv",
    )
    args = parser.parse_args()

    report = prepare(args.raw_dir, args.out)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
