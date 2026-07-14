from __future__ import annotations

import csv
from pathlib import Path

from scripts.build_phi_r_figure import build_phi_r_figure


def test_build_phi_r_figure_requires_and_preserves_frozen_six_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text(
        "dataset,corruption_level,phi_R,source_status,allowed_use\n"
        "Beauty,c0,1.0,preregistered_artifact,figure\n"
        "Beauty,c60,0.1366311174092942,preregistered_artifact,figure\n"
        "Beauty,c100,0.0,preregistered_artifact,figure\n"
        "Steam,c0,1.0,preregistered_artifact,figure\n"
        "Steam,c60,0.05808110271503808,preregistered_artifact,figure\n"
        "Steam,c100,0.0,preregistered_artifact,figure\n",
        encoding="utf-8",
    )
    output = tmp_path / "figure"

    manifest = build_phi_r_figure(source, output)

    assert (tmp_path / "figure.pdf").stat().st_size > 0
    assert (tmp_path / "figure.png").stat().st_size > 0
    rows = list(csv.DictReader(source.open(encoding="utf-8")))
    assert manifest["row_count"] == len(rows) == 6
    assert manifest["values"]["Beauty"]["c60"] == 0.1366311174092942
    assert manifest["values"]["Steam"]["c60"] == 0.05808110271503808
    assert manifest["interpretation"] == "preregistered intervention; not performance"
