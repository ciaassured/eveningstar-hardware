#!/usr/bin/env python3

"""Generate deterministic JLCPCB production artifacts from a KiCad board."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile


GERBER_TIMESTAMP_PATTERNS = (
    (
        re.compile(r"(?m)^((?:G04 #@! |%)TF\.CreationDate,)[^*\r\n]+(\*%?)$"),
        r"\g<1>1970-01-01T00:00:00+00:00\g<2>",
    ),
    (
        re.compile(r"(?m)^(G04 Created by KiCad \([^\r\n]+\) date )[^*\r\n]+(\*)$"),
        r"\g<1>1970-01-01 00:00:00\g<2>",
    ),
    (
        re.compile(r"(?m)^(; DRILL file KiCad [^\r\n]+ date )[^\r\n]+$"),
        r"\g<1>1970-01-01T00:00:00",
    ),
    (
        re.compile(r"(?m)^(; #@! TF\.CreationDate,)[^\r\n]+$"),
        r"\g<1>1970-01-01T00:00:00+00:00",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--toolkit", required=True, type=Path)
    return parser.parse_args()


def normalize_timestamps(path: Path) -> None:
    contents = path.read_text(encoding="utf-8")
    for pattern, replacement in GERBER_TIMESTAMP_PATTERNS:
        contents = pattern.sub(replacement, contents)
    path.write_text(contents, encoding="utf-8", newline="")


def normalize_ipcd356(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines[:3] != ["P  CODE 00", "P  UNITS CUST 0", "P  arrayDim   N"]:
        raise RuntimeError(f"unexpected IPC-D-356 header in {path}")
    if lines[-1:] != ["999"]:
        raise RuntimeError(f"unexpected IPC-D-356 terminator in {path}")
    path.write_text(
        "\n".join([*lines[:3], *sorted(lines[3:-1]), lines[-1], ""]),
        encoding="utf-8",
        newline="",
    )


def write_deterministic_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for path in sorted(source.iterdir(), key=lambda item: item.name):
            info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(args.toolkit))

    from plugins.process import (  # type: ignore  # pylint: disable=import-error,import-outside-toplevel
        ProcessManager,
    )
    import pcbnew  # type: ignore  # pylint: disable=import-error,import-outside-toplevel

    board = pcbnew.LoadBoard(str(args.board.resolve()))
    manager = ProcessManager(board)

    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="eveningstar-production-") as temporary:
        temporary_path = Path(temporary)
        gerber_path = temporary_path / "gerbers"
        tables_path = temporary_path / "tables"
        gerber_path.mkdir()
        tables_path.mkdir()

        manager.generate_gerber(
            str(gerber_path),
            extra_layers="",
            extend_edge_cuts=False,
            alternative_edge_cuts=False,
            all_active_layers=False,
        )
        manager.generate_drills(str(gerber_path))
        manager.generate_netlist(str(tables_path))
        normalize_ipcd356(tables_path / "netlist.ipc")
        manager.generate_tables(
            str(tables_path), auto_translate=True, exclude_dnp=False
        )

        manager.generate_positions(str(tables_path))
        manager.generate_bom(str(tables_path))

        gerber_files = sorted(path for path in gerber_path.iterdir() if path.is_file())
        if len(gerber_files) != 13:
            raise RuntimeError(
                f"expected 13 Gerber/drill files, generated {len(gerber_files)}"
            )
        for path in gerber_files:
            normalize_timestamps(path)

        write_deterministic_zip(gerber_path, args.output / "EveningStar.zip")
        for name in ("bom.csv", "designators.csv", "netlist.ipc", "positions.csv"):
            shutil.copyfile(tables_path / name, args.output / name)


if __name__ == "__main__":
    os.environ.setdefault("TZ", "UTC")
    main()
