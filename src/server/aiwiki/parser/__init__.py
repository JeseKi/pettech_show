# -*- coding: utf-8 -*-
"""Parse generated AI Wiki artifacts into display-oriented JSON."""

from __future__ import annotations

from pathlib import Path

from ..schemas import AiwikiResultOut
from .collections import (
    build_navigation,
    build_summary,
    collect_highlight_terms,
    collect_named_assets,
    collect_search_intents,
    collect_topics,
)
from .materials import parse_materials
from .wiki import attach_reference_links, parse_wiki_entries, parse_wiki_home


def parse_aiwiki_result(job_id: str, workdir: Path) -> AiwikiResultOut:
    materials = parse_materials(workdir)
    wiki_home = parse_wiki_home(workdir)
    wiki_entries = parse_wiki_entries(workdir)
    attach_reference_links(wiki_entries)
    search_intents = collect_search_intents(materials, wiki_entries)

    return AiwikiResultOut(
        job_id=job_id,
        summary=build_summary(materials, wiki_entries, search_intents),
        materials=materials,
        hotspots=collect_named_assets(materials, wiki_entries, "hotspot", "hotspots"),
        pain_points=collect_named_assets(
            materials, wiki_entries, "pain_point", "pain_points"
        ),
        solutions=collect_named_assets(materials, wiki_entries, "solution", "solutions"),
        topics=collect_topics(materials, wiki_entries),
        search_intents=search_intents,
        wiki_home=wiki_home,
        wiki_entries=wiki_entries,
        highlight_terms=collect_highlight_terms(materials, wiki_entries),
        navigation=build_navigation(wiki_entries, materials),
    )


__all__ = ["parse_aiwiki_result"]
