# -*- coding: utf-8 -*-
"""Constants for daily writer jobs."""

DAILY_WRITER_SKILL_NAME = "wechat-daily-writer"
VARIANT_BATCH_SKILL_NAME = "wechat-main-variant-batch-rewriter"
VARIANT_REWRITER_SKILL_NAME = "wechat-main-variant-rewriter"
ARTWORK_COORDINATOR_SKILL_NAME = "wechat-main-artwork-coordinator"
GUIZANG_SOCIAL_CARD_SKILL_NAME = "guizang-social-card-skill"
DAILY_WRITER_SKILL_NAMES = [
    DAILY_WRITER_SKILL_NAME,
    VARIANT_BATCH_SKILL_NAME,
    VARIANT_REWRITER_SKILL_NAME,
]
ARTWORK_SKILL_NAMES = [
    ARTWORK_COORDINATOR_SKILL_NAME,
    GUIZANG_SOCIAL_CARD_SKILL_NAME,
]
MAX_VARIANT_COUNT = 5
SELECTED_SEED_ROW_PATH = "input/selected_seed_row.json"
RESULT_ZIP_NAME = "daily_writer_result.zip"
