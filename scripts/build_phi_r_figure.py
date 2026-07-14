from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


EXPECTED = {"Beauty": {"c0", "c60", "c100"}, "Steam": {"c0", "c60", "c100"}}


def build_phi_r_figure(source: Path, output_stem: Path) -> dict[str, object]:
    import matplotlib.pyplot as plt

    source = Path(source)
    rows = list(csv.DictReader(source.open(encoding="utf-8-sig", newline="")))
    values: dict[str, dict[str, float]] = {"Beauty": {}, "Steam": {}}
    for row in rows:
        dataset, level = row["dataset"], row["corruption_level"]
        if dataset not in EXPECTED or level not in EXPECTED[dataset]:
            raise ValueError(f"unexpected phi_R row: {dataset}/{level}")
        if level in values[dataset]:
            raise ValueError(f"duplicate phi_R row: {dataset}/{level}")
        values[dataset][level] = float(row["phi_R"])
    if len(rows) != 6 or any(set(values[d]) != EXPECTED[d] for d in EXPECTED):
        raise ValueError("phi_R source must contain the frozen six-row matrix")

    x = [0, 60, 100]
    fig, ax = plt.subplots(figsize=(4.6, 2.8), constrained_layout=True)
    for dataset, color, marker in (("Beauty", "#2E86AB", "o"), ("Steam", "#C73E1D", "s")):
        y = [values[dataset][f"c{level}"] for level in x]
        ax.plot(x, y, marker=marker, linewidth=2, markersize=5, color=color, label=dataset)
    ax.set_xlabel("Embedding corruption level (%)")
    ax.set_ylabel(r"Preregistered $\phi_R$")
    ax.set_xticks(x)
    ax.set_ylim(-0.04, 1.06)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    pdf, png = output_stem.with_suffix(".pdf"), output_stem.with_suffix(".png")
    fig.savefig(pdf)
    fig.savefig(png, dpi=300)
    plt.close(fig)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "row_count": len(rows),
        "values": values,
        "interpretation": "preregistered intervention; not performance",
        "outputs": [str(pdf), str(png)],
    }
    output_stem.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-stem", type=Path, required=True)
    args = parser.parse_args()
    build_phi_r_figure(args.source, args.output_stem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
