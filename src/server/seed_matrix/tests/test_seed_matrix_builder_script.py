# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


def test_seed_matrix_builder_expands_to_max_seeds(tmp_path: Path):
    material_dir = tmp_path / "material" / "260620"
    material_dir.mkdir(parents=True)
    (material_dir / "sample.json").write_text(
        json.dumps(
            {
                "元数据": {"标题": "新手养宠避坑"},
                "选题": ["新手养宠第一天怎么做？", "新手养宠怎么喂？"],
                "总结": {
                    "核心热点": "新手养宠",
                    "核心痛点": "不知道如何安全开始养宠",
                    "核心解决方案": "按清单和时间线执行",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "seed_matrix.csv"

    subprocess.run(
        [
            "python3",
            ".agents/skills/wechat-seed-matrix-builder/scripts/build_seed_matrix.py",
            "--material-dir",
            material_dir.as_posix(),
            "--output",
            output.as_posix(),
            "--seeds-per-material",
            "6",
            "--max-seeds",
            "6",
        ],
        check=True,
    )

    with output.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 6
    assert rows[0]["seed_id"] == "S001"
    assert rows[-1]["seed_id"] == "S006"
    assert "｜" in rows[-1]["topic"]
