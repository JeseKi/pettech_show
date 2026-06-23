# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
TOPIC_VALIDATOR = PROJECT_ROOT / ".agents" / "skills" / "zhongying-topic-planner" / "scripts" / "validate_result.py"
SCRIPT_VALIDATOR = PROJECT_ROOT / ".agents" / "skills" / "zhongying-script-creator" / "scripts" / "validate_result.py"


def _write_common_result(workdir: Path, data: dict) -> None:
    output = workdir / "output"
    output.mkdir(parents=True)
    (output / "result.md").write_text("# Result\n\ncontent\n", encoding="utf-8")
    (output / "result.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _run_validator(script: Path, workdir: Path, capability_key: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script.as_posix(), "--workdir", workdir.as_posix(), "--capability-key", capability_key],
        check=False,
        capture_output=True,
        text=True,
    )


def test_topic_validator_accepts_valid_result(tmp_path: Path):
    _write_common_result(
        tmp_path,
        {
            "title": "痛点选题池",
            "capability_key": "pain-point-topics",
            "summary": {},
            "sections": [{"title": "结论"}],
            "topics": [
                {
                    "title": "猫咪呕吐后哪些情况必须就医",
                    "category": "症状判断",
                    "total_score": 58,
                    "recommended_hook": "猫吐一次不一定要慌",
                }
            ],
            "next_actions": ["进入脚本创作"],
        },
    )
    result = _run_validator(TOPIC_VALIDATOR, tmp_path, "pain-point-topics")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK topic planning output" in result.stdout


def test_topic_validator_rejects_invalid_json(tmp_path: Path):
    output = tmp_path / "output"
    output.mkdir(parents=True)
    (output / "result.md").write_text("# Result\n", encoding="utf-8")
    (output / "result.json").write_text(
        '{"title": "痛点选题池", "capability_key": "pain-point-topics", "topics": [{"title": "一例"坏 JSON"标题"}]}',
        encoding="utf-8",
    )
    result = _run_validator(TOPIC_VALIDATOR, tmp_path, "pain-point-topics")
    assert result.returncode == 1
    assert "invalid JSON" in result.stdout


def test_topic_validator_rejects_missing_topics(tmp_path: Path):
    _write_common_result(
        tmp_path,
        {
            "title": "痛点选题池",
            "capability_key": "pain-point-topics",
            "summary": {},
            "sections": [{"title": "结论"}],
            "next_actions": ["进入脚本创作"],
        },
    )
    result = _run_validator(TOPIC_VALIDATOR, tmp_path, "pain-point-topics")
    assert result.returncode == 1
    assert "topics" in result.stdout


def test_script_validator_accepts_valid_result(tmp_path: Path):
    _write_common_result(
        tmp_path,
        {
            "title": "脚本母版生成",
            "capability_key": "script-master-draft",
            "summary": {},
            "sections": [{"title": "脚本结构"}],
            "scenes": [
                {
                    "scene": "开头",
                    "visual": "医生正面口播",
                    "voiceover": "猫吐一次不一定要慌。",
                }
            ],
            "next_actions": ["拍摄"],
        },
    )
    result = _run_validator(SCRIPT_VALIDATOR, tmp_path, "script-master-draft")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK script creation output" in result.stdout


def test_script_validator_rejects_missing_script_content(tmp_path: Path):
    _write_common_result(
        tmp_path,
        {
            "title": "脚本母版生成",
            "capability_key": "script-master-draft",
            "summary": {},
            "sections": [{"title": "脚本结构"}],
            "next_actions": ["拍摄"],
        },
    )
    result = _run_validator(SCRIPT_VALIDATOR, tmp_path, "script-master-draft")
    assert result.returncode == 1
    assert "scenes or script content" in result.stdout
