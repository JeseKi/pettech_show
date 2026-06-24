# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

from src.server.agent_skills.models import AgentSkill, AgentSkillCategory, AgentSkillUsageEvent, UserAgentSkill
from src.server.aiwiki.models import AiwikiJob
from src.server.auth.models import User
from src.server.capability_jobs.models import CapabilityJob
from src.server.daily_writer.models import DailyWriterJob
from src.server.interactive_movie.models import (
    InteractiveMovieProject,
    InteractiveMovieScene,
    InteractiveMovieScriptLine,
)
from src.server.seed_matrix.models import SeedMatrixJob


def _login_admin(test_client):
    resp = test_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == HTTPStatus.OK, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_monitoring_overview_summarizes_core_modules(test_client, test_db_session, init_test_database):
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    old = now - timedelta(days=20)

    admin = test_db_session.query(User).filter(User.username == "admin").first()
    assert admin is not None

    test_db_session.add(
        AiwikiJob(
            id="aiwiki-monitoring",
            owner_user_id=admin.id,
            status="completed",
            title="资产任务",
            workdir="/tmp/aiwiki-monitoring",
            raw_date="260625",
            files_json="[]",
            summary_json=json.dumps(
                {
                    "material_count": 2,
                    "wiki_entry_count": 3,
                    "search_intent_count": 4,
                    "topic_count": 5,
                }
            ),
            created_at=old,
            finished_at=yesterday,
            updated_at=yesterday,
        )
    )
    test_db_session.add(
        SeedMatrixJob(
            id="seed-monitoring",
            owner_user_id=admin.id,
            source_aiwiki_job_id="aiwiki-monitoring",
            status="completed",
            workdir="/tmp/seed-monitoring",
            params_json=json.dumps({"expected_seed_count": 50, "slots_per_day": 5, "hooks": []}),
            result_csv_path="matrix.csv",
            summary_json=json.dumps({"seed_count": 12}),
            created_at=yesterday,
            finished_at=yesterday,
            updated_at=yesterday,
        )
    )
    test_db_session.add(
        DailyWriterJob(
            id="daily-monitoring",
            owner_user_id=admin.id,
            source_seed_matrix_job_id="seed-monitoring",
            source_aiwiki_job_id="aiwiki-monitoring",
            seed_id="seed-1",
            status="completed",
            workdir="/tmp/daily-monitoring",
            row_json="{}",
            params_json=json.dumps({"generate_variants": True, "variant_count": 4}),
            article_path="main.md",
            summary_json=json.dumps({"variant_success_count": 4}),
            created_at=yesterday,
            finished_at=yesterday,
            updated_at=yesterday,
        )
    )
    test_db_session.add(
        CapabilityJob(
            id="script-monitoring",
            owner_user_id=admin.id,
            capability_key="script-master-draft",
            status="completed",
            workdir="/tmp/script-monitoring",
            input_json="{}",
            summary_json="{}",
            created_at=yesterday,
            finished_at=yesterday,
            updated_at=yesterday,
        )
    )
    test_db_session.add(AgentSkillCategory(id="ops", name="运营", description="", sort_order=1, enabled=True, created_at=old, updated_at=old))
    test_db_session.add(
        AgentSkill(
            id="skill-monitoring",
            slug="skill-monitoring",
            title="监控 Skill",
            category_id="ops",
            visibility="public",
            summary="监控",
            description="监控",
            skill_dir="/tmp/skill",
            skill_path="/tmp/skill/SKILL.md",
            metadata_path="/tmp/skill/agents/openai.yaml",
            sort_order=1,
            enabled=True,
            created_at=old,
            updated_at=old,
        )
    )
    test_db_session.flush()
    test_db_session.add(UserAgentSkill(owner_user_id=admin.id, skill_id="skill-monitoring", enabled=True, created_at=yesterday, updated_at=yesterday))
    test_db_session.add(AgentSkillUsageEvent(owner_user_id=admin.id, skill_id="skill-monitoring", action="add", created_at=yesterday))
    test_db_session.add(AgentSkillUsageEvent(owner_user_id=admin.id, skill_id="skill-monitoring", action="remove", created_at=yesterday))
    test_db_session.add(
        InteractiveMovieProject(
            id="movie-monitoring",
            owner_user_id=admin.id,
            title="互动电影",
            canvas_json="{}",
            version=1,
            content_hash="hash",
            created_at=yesterday,
            updated_at=yesterday,
        )
    )
    test_db_session.add(
        InteractiveMovieScene(
            id="scene-monitoring",
            project_id="movie-monitoring",
            title="开场",
            role="start",
            updated_at=yesterday,
        )
    )
    test_db_session.add(
        InteractiveMovieScriptLine(
            id="line-monitoring",
            scene_id="scene-monitoring",
            speaker="角色",
            text="台词",
            sort_order=1,
        )
    )
    test_db_session.commit()

    headers = _login_admin(test_client)
    resp = test_client.get(
        "/api/admin/monitoring/overview",
        params={
            "start_at": (now - timedelta(days=7)).isoformat(),
            "end_at": now.isoformat(),
        },
        headers=headers,
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    payload = resp.json()
    modules = {item["key"]: item for item in payload["modules"]}
    assert modules["aiwiki"]["cards"][0]["value"] == 14
    assert modules["aiwiki"]["cards"][0]["range_value"] == 14
    assert modules["seed-matrix"]["cards"][1]["value"] == 12
    assert modules["daily-writer"]["cards"][1]["value"] == 5
    assert modules["scripts"]["cards"][0]["value"] == 1
    assert modules["agent-skills"]["cards"][3]["value"] == 1
    assert modules["interactive-movie"]["cards"][2]["value"] == 1


def test_monitoring_requires_admin(test_client, test_db_session):
    user = User(username="monitor_member", email="monitor_member@example.com")
    user.set_password("Password123")
    test_db_session.add(user)
    test_db_session.commit()

    login_resp = test_client.post(
        "/api/auth/login",
        json={"username": "monitor_member", "password": "Password123"},
    )
    assert login_resp.status_code == HTTPStatus.OK, login_resp.text
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = test_client.get("/api/admin/monitoring/overview", headers=headers)

    assert resp.status_code == HTTPStatus.FORBIDDEN
