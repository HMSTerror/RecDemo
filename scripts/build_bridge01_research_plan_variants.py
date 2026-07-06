#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CN_SOURCE = REPO_ROOT / "future_work" / "07-bridge01-research-plan-cn.md"
DEFAULT_EN_SOURCE = REPO_ROOT / "future_work" / "07-bridge01-research-plan-en.md"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "future_work"

CN_MARKERS = ("## 4A. 团队钩子（Lumina 版本）", "## 4B. 团队钩子（InternVideo 版本）")
EN_MARKERS = ("## 4A. Team hook (Lumina variant)", "## 4B. Team hook (InternVideo variant)")


def split_variant_sections(text: str, first_marker: str, second_marker: str) -> tuple[str, str, str]:
    if first_marker not in text or second_marker not in text:
        raise ValueError("source document is missing variant markers")
    prefix, rest = text.split(first_marker, 1)
    first_body, second_body = rest.split(second_marker, 1)
    return prefix.rstrip() + "\n\n", first_body.strip() + "\n", second_body.strip() + "\n"


def compose_variant(prefix: str, heading: str, body: str) -> str:
    return prefix + heading + "\n\n" + body.strip() + "\n"


def build_variants(
    *,
    cn_source: Path,
    en_source: Path,
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    cn_prefix, cn_lumina, cn_internvideo = split_variant_sections(
        cn_source.read_text(encoding="utf-8"),
        *CN_MARKERS,
    )
    en_prefix, en_lumina, en_internvideo = split_variant_sections(
        en_source.read_text(encoding="utf-8"),
        *EN_MARKERS,
    )

    outputs = {
        output_dir / "07-bridge01-research-plan-cn-lumina.md": compose_variant(cn_prefix, "## 4. 团队钩子", cn_lumina),
        output_dir / "07-bridge01-research-plan-cn-internvideo.md": compose_variant(
            cn_prefix,
            "## 4. 团队钩子",
            cn_internvideo,
        ),
        output_dir / "07-bridge01-research-plan-en-lumina.md": compose_variant(en_prefix, "## 4. Team hook", en_lumina),
        output_dir / "07-bridge01-research-plan-en-internvideo.md": compose_variant(
            en_prefix,
            "## 4. Team hook",
            en_internvideo,
        ),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
    return list(outputs.keys())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build BRIDGE-01 team-specific CN/EN one-page variants.")
    parser.add_argument("--cn-source", type=Path, default=DEFAULT_CN_SOURCE)
    parser.add_argument("--en-source", type=Path, default=DEFAULT_EN_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = build_variants(
        cn_source=args.cn_source,
        en_source=args.en_source,
        output_dir=args.output_dir,
    )
    for path in outputs:
        print(f"WROTE {path}")


if __name__ == "__main__":
    main()
