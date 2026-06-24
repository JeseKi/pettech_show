# -*- coding: utf-8 -*-
"""DAO helpers for agent marketplace."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.server.dao.dao_base import BaseDAO

from .models import Agent, AgentCategory, AgentPromptRevision, AgentTag


class AgentMarketDAO(BaseDAO):
    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def get_agent(self, agent_id: str) -> Agent | None:
        return self.db_session.query(Agent).filter(Agent.id == agent_id).first()

    def get_category(self, category_id: str) -> AgentCategory | None:
        return self.db_session.query(AgentCategory).filter(AgentCategory.id == category_id).first()

    def get_tag(self, tag_id: str) -> AgentTag | None:
        return self.db_session.query(AgentTag).filter(AgentTag.id == tag_id).first()

    def get_revision(self, revision_id: str) -> AgentPromptRevision | None:
        return (
            self.db_session.query(AgentPromptRevision)
            .filter(AgentPromptRevision.id == revision_id)
            .first()
        )

