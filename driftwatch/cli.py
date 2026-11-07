"""DriftWatch command line. `python -m driftwatch.cli report --site 03459500`.

Writes reports/<site>.json (Report schema) and prints one line per site.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from driftwatch.modules.rating_curve import report as rc_report
from driftwatch.modules.rating_curve.usgs import SITES

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def write_report(rep, reports_dir: Path | None = None) -> Path:
    out = (reports_dir or REPORTS_DIR) / f"{rep.site}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(rep.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="driftwatch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("report", help="build reports/<site>.json from the snapshot")
    rp.add_argument("--site", nargs="+", default=None, help="site id(s); default: all 8")
    rp.add_argument("--source", choices=("snapshot", "live"), default="snapshot")
    rp.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    # Pairing drop counts etc. go to stderr; the summary lines stay alone on stdout.
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    if args.source != "snapshot":
        print(
            "reports read the snapshot only; run make snapshot SOURCE=live first", file=sys.stderr
        )
        return 2
    for site in args.site or SITES:
        rep = rc_report.build_report(site, args.source)
        write_report(rep, args.out)
        print(rc_report.summary_line(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
