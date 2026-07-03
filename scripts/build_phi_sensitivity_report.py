"""Phi-hinge sensitivity analysis over frozen artifacts (observation only).

Inputs (frozen, cited):
- U_ds per dataset: docs/reports/data/2026-07-02-gate0/gate0_text_utility_summary.csv
- First-generation delta test p2 NDCG@10 vs core:
  docs/reports/data/2026-07-01-text-side-vs-core-main-table-remote-v77.csv

Sweeps hinge parameters (U_hi, width) for phi(U) = clip((U_hi - U)/width, 0, 1)
and reports, per grid point:
- phi per dataset
- ml1m_closed  := phi(ML1M) <= 0.2   (frozen Gate 0-v2 condition-2 analogue)
- steam_open   := phi(Steam) >= 0.5  (condition-3 analogue, Steam arm)
- harm_admitted := sum phi_ds * max(0, -delta_ds)
- gain_admitted := sum phi_ds * max(0,  delta_ds)
No frozen parameter is modified; the frozen point (0.70, 0.10) is only located
within the grid. Also reports leave-one-out inversion of the U_ds/delta ranks.
"""
from __future__ import annotations

import csv
from itertools import permutations
from pathlib import Path

# frozen inputs (see module docstring for artifact provenance)
U_DS = {"Steam": 0.569566, "ATG": 0.688262, "Beauty": 0.712427, "ML1M": 0.753539}
DELTA = {"Steam": 0.006388, "ATG": 0.001911, "Beauty": -0.000613, "ML1M": -0.062177}
FROZEN = (0.70, 0.10)
U_HI_GRID = [round(0.60 + 0.01 * i, 2) for i in range(23)]  # 0.60 .. 0.82
WIDTH_GRID = [0.05, 0.10, 0.15, 0.20]


def phi(u: float, u_hi: float, width: float) -> float:
    return min(1.0, max(0.0, (u_hi - u) / width))


def spearman_sign(xs: list[float], ys: list[float]) -> float:
    rx = {v: r for r, v in enumerate(sorted(xs))}
    ry = {v: r for r, v in enumerate(sorted(ys))}
    n = len(xs)
    d2 = sum((rx[x] - ry[y]) ** 2 for x, y in zip(xs, ys))
    return 1 - 6 * d2 / (n * (n * n - 1))


def loo_inversion() -> list[tuple[str, float, float]]:
    out = []
    names = list(U_DS)
    for left_out in names:
        keep = [n for n in names if n != left_out]
        rho = spearman_sign([U_DS[n] for n in keep], [DELTA[n] for n in keep])
        n = len(keep)
        exact_p = sum(
            1
            for p in permutations(range(n))
            if spearman_sign(list(range(n)), list(p)) <= rho
        ) / len(list(permutations(range(n))))
        out.append((left_out, rho, exact_p))
    return out


def build(out_csv: Path, out_md: Path) -> dict:
    rows = []
    for u_hi in U_HI_GRID:
        for width in WIDTH_GRID:
            phis = {d: phi(u, u_hi, width) for d, u in U_DS.items()}
            rows.append(
                {
                    "u_hi": u_hi,
                    "width": width,
                    **{f"phi_{d}": round(phis[d], 4) for d in U_DS},
                    "ml1m_closed": int(phis["ML1M"] <= 0.2),
                    "steam_open": int(phis["Steam"] >= 0.5),
                    "harm_admitted": round(
                        sum(phis[d] * max(0.0, -DELTA[d]) for d in U_DS), 6
                    ),
                    "gain_admitted": round(
                        sum(phis[d] * max(0.0, DELTA[d]) for d in U_DS), 6
                    ),
                    "is_frozen_point": int((u_hi, width) == FROZEN),
                }
            )
    ok = [r for r in rows if r["ml1m_closed"] and r["steam_open"]]
    frozen_row = next(r for r in rows if r["is_frozen_point"])
    summary = {
        "grid_size": len(rows),
        "pass_count": len(ok),
        "pass_fraction": round(len(ok) / len(rows), 4),
        "u_hi_pass_range": (
            min(r["u_hi"] for r in ok),
            max(r["u_hi"] for r in ok),
        )
        if ok
        else None,
        "frozen_in_pass_region": bool(frozen_row["ml1m_closed"] and frozen_row["steam_open"]),
        "frozen_harm_admitted": frozen_row["harm_admitted"],
        "frozen_gain_admitted": frozen_row["gain_admitted"],
        "full_rank_rho": spearman_sign(list(U_DS.values()), list(DELTA.values())),
        "loo": loo_inversion(),
    }
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# phi hinge sensitivity (observation only)\n\n")
        f.write(f"- grid: {len(rows)} points; pass (ml1m_closed AND steam_open): ")
        f.write(f"{summary['pass_count']} ({summary['pass_fraction']:.0%})\n")
        f.write(f"- passing U_hi range: {summary['u_hi_pass_range']}\n")
        f.write(f"- frozen point (0.70, 0.10) in pass region: {summary['frozen_in_pass_region']}\n")
        f.write(f"- frozen harm/gain admitted: {summary['frozen_harm_admitted']} / {summary['frozen_gain_admitted']}\n")
        f.write(f"- full-rank Spearman rho(U_ds, delta): {summary['full_rank_rho']}\n")
        f.write("- leave-one-out inversion: " + "; ".join(
            f"drop {n}: rho={r:.0f}, exact p={p:.3f}" for n, r, p in summary["loo"]
        ) + "\n")
    return summary


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    s = build(
        root / "docs/reports/data/2026-07-04-phi-sensitivity-grid.csv",
        root / "docs/reports/data/2026-07-04-phi-sensitivity-summary.md",
    )
    for k, v in s.items():
        print(k, "=", v)
