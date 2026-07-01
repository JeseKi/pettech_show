# -*- coding: utf-8 -*-
"""Filesystem artifact helpers for social card jobs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.server.config import global_config
from src.server.daily_writer.models import DailyWriterJob
from src.server.daily_writer.parser import resolve_result_paths

from .constants import SOCIAL_CARD_SKILL_NAMES, SOURCE_MAIN_PATH, SOURCE_METADATA_PATH


def copy_source_article(source_job: DailyWriterJob, target_workdir: Path) -> None:
    source_article, source_metadata = resolve_result_paths(
        Path(source_job.workdir),
        article_path=source_job.article_path,
        metadata_path=source_job.metadata_path,
    )
    target_article = target_workdir / SOURCE_MAIN_PATH
    target_metadata = target_workdir / SOURCE_METADATA_PATH
    target_article.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_article, target_article)
    shutil.copyfile(source_metadata, target_metadata)
    (target_workdir / "source" / "source_job.json").write_text(
        json.dumps(
            {
                "source_daily_writer_job_id": source_job.id,
                "source_article_path": source_article.relative_to(Path(source_job.workdir)).as_posix(),
                "source_metadata_path": source_metadata.relative_to(Path(source_job.workdir)).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def prepare_skill(workdir: Path) -> None:
    source_root = Path(global_config.project_root) / ".agents" / "skills"
    target_root = workdir / ".agents" / "skills"
    target_root.mkdir(parents=True, exist_ok=True)
    for skill_name in SOCIAL_CARD_SKILL_NAMES:
        source = source_root / skill_name
        if not source.exists():
            raise RuntimeError(f"Skill 不存在：{source}")
        target = target_root / skill_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    _copy_agent_assets(workdir)
    write_render_helper(workdir)


def _copy_agent_assets(workdir: Path) -> None:
    source = Path(global_config.project_root) / ".agents" / "assets"
    if not source.exists():
        return
    target = workdir / ".agents" / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def write_render_helper(workdir: Path) -> None:
    tools_dir = workdir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "render_social_deck.mjs").write_text(
        SOCIAL_CARD_RENDER_HELPER,
        encoding="utf-8",
    )


SOCIAL_CARD_RENDER_HELPER = r"""#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';

const args = process.argv.slice(2);
const deckArg = args.find((arg) => !arg.startsWith('--')) || 'xhs_guizang';
const countArg = readFlag('--count');
const width = Number(readFlag('--width') || 1080);
const height = Number(readFlag('--height') || 1440);
const root = process.cwd();
const deckDir = path.resolve(root, deckArg);
const manifestPath = path.join(deckDir, 'manifest.json');
const indexPath = path.join(deckDir, 'index.html');

function readFlag(name) {
  const index = args.indexOf(name);
  if (index === -1) return '';
  return args[index + 1] || '';
}

async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    '/usr/bin/google-chrome',
    '/usr/local/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (await fileExists(candidate)) return candidate;
  }
  throw new Error('No local Chrome/Chromium executable found');
}

async function readManifest() {
  const raw = await fs.readFile(manifestPath, 'utf8');
  return JSON.parse(raw);
}

function manifestImages(manifest) {
  const source = Array.isArray(manifest.cards)
    ? manifest.cards
    : Array.isArray(manifest.uploaded_images)
      ? manifest.uploaded_images
      : [];
  return source
    .map((item) => {
      if (!item || typeof item !== 'object') return '';
      return item.file || item.path || item.output || item.filename || '';
    })
    .filter((value) => typeof value === 'string' && value.endsWith('.png'));
}

function defaultImages(count) {
  return Array.from({ length: count }, (_, index) => (
    `output/xhs-${String(index + 1).padStart(2, '0')}.png`
  ));
}

function runChrome(chrome, imagePath, cardIndex) {
  const targetUrl = `${pathToFileURL(indexPath).href}?card=${cardIndex}`;
  const screenshotPath = path.resolve(deckDir, imagePath);
  return new Promise((resolve, reject) => {
    const child = spawn(chrome, [
      '--headless=new',
      '--no-sandbox',
      '--disable-gpu',
      '--hide-scrollbars',
      `--window-size=${width},${height}`,
      '--force-device-scale-factor=1',
      `--screenshot=${screenshotPath}`,
      targetUrl,
    ], { stdio: 'ignore' });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Chrome exited with code ${code}`));
    });
  });
}

if (!(await fileExists(indexPath))) {
  throw new Error(`Missing index.html: ${indexPath}`);
}
const manifest = await readManifest();
const expectedCount = Number(countArg || manifest.total_card_count || manifest.pages || 0);
const images = manifestImages(manifest);
const outputImages = images.length ? images : defaultImages(expectedCount);
if (!outputImages.length) {
  throw new Error('No output images found in manifest and --count was not provided');
}
if (expectedCount && outputImages.length !== expectedCount) {
  throw new Error(`Image count mismatch: expected ${expectedCount}, got ${outputImages.length}`);
}

const chrome = await findChrome();
for (const image of outputImages) {
  await fs.mkdir(path.dirname(path.resolve(deckDir, image)), { recursive: true });
}
for (let index = 0; index < outputImages.length; index += 1) {
  await runChrome(chrome, outputImages[index], index);
}
console.log(JSON.stringify({ deck: path.relative(root, deckDir), count: outputImages.length, chrome }));
"""
