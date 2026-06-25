import Graph from 'graphology'
import type { AiwikiResult, AiwikiWikiEntry } from '../../lib/aiwiki'
import { entryTypeLabel } from './helpers'
import { colorForKind, radiusForKind } from './graphStyles'

export type GraphKind = 'home' | 'entry' | 'type' | 'tag' | 'keyword'

export interface KnowledgeGraphNodeAttributes {
  x: number
  y: number
  size: number
  label: string
  fullLabel: string
  color: string
  kind: GraphKind
  chargeStrength: number
  degree: number
  entrySlug?: string
  forceLabel?: boolean
  highlighted?: boolean
  neighborIds: string[]
  radius: number
}

export interface KnowledgeGraphEdgeAttributes {
  color: string
  size: number
  kind: GraphKind
}

export type KnowledgeGraphModel = Graph<
  KnowledgeGraphNodeAttributes,
  KnowledgeGraphEdgeAttributes
>

export function buildKnowledgeGraph(result: AiwikiResult) {
  const graph: KnowledgeGraphModel = new Graph({ type: 'undirected', multi: false })
  const entries = result.wiki_entries

  addNode(graph, 'home', result.wiki_home?.title ?? '内容资产库', 'home', undefined, undefined, true)
  entries.forEach((entry) => {
    addNode(graph, entry.slug, entry.title, 'entry', entry.slug, entry.type)
    addEdge(graph, 'home', entry.slug, 'home')
  })

  entries.forEach((entry) => {
    const typeId = `type:${entry.type}`
    addNode(graph, typeId, entryTypeLabel(entry.type), 'type')
    addEdge(graph, typeId, entry.slug, 'type')

    extractTags(entry).slice(0, 5).forEach((tag) => {
      const tagId = `tag:${tag}`
      addNode(graph, tagId, tag, 'tag')
      addEdge(graph, tagId, entry.slug, 'tag')
    })

    entry.reference_links.forEach((ref) => addEdge(graph, entry.slug, ref.slug, 'entry'))
  })

  result.highlight_terms.slice(0, 40).forEach((keyword) => {
    const matchedEntries = entries.filter((entry) => entryMatchesKeyword(entry, keyword)).slice(0, 8)
    if (!matchedEntries.length) return
    const keywordId = `keyword:${keyword}`
    addNode(graph, keywordId, keyword, 'keyword')
    matchedEntries.forEach((entry) => addEdge(graph, keywordId, entry.slug, 'keyword'))
  })

  applyNodePhysicsAttributes(graph)
  return { graph, entryCount: entries.length }
}

function addNode(
  graph: KnowledgeGraphModel,
  id: string,
  label: string,
  kind: GraphKind,
  entrySlug?: string,
  entryType?: string,
  forceLabel = false,
) {
  if (graph.hasNode(id)) return
  const radius = radiusForKind(kind)
  graph.addNode(id, {
    x: seeded(id, 0) * 72 - 36,
    y: seeded(id, 1) * 72 - 36,
    size: radius,
    label: truncate(label, kind === 'entry' ? 28 : 18),
    fullLabel: label,
    color: colorForKind(kind, entryType),
    kind,
    chargeStrength: -120,
    degree: 0,
    entrySlug,
    forceLabel,
    neighborIds: [],
    radius,
  })
}

function addEdge(graph: KnowledgeGraphModel, source: string, target: string, kind: GraphKind) {
  if (!graph.hasNode(source) || !graph.hasNode(target) || graph.hasEdge(source, target)) return
  graph.addUndirectedEdge(source, target, {
    color: edgeColor(kind),
    size: kind === 'entry' ? 1.25 : 0.85,
    kind,
  })
}

function edgeColor(kind: GraphKind) {
  if (kind === 'home') return '#818cf8'
  if (kind === 'entry') return '#64748b'
  if (kind === 'keyword') return '#86efac'
  if (kind === 'tag') return '#fbbf24'
  return '#c4b5fd'
}

function extractTags(entry: AiwikiWikiEntry) {
  const tags = entry.frontmatter.tags
  return Array.isArray(tags) ? tags.filter((item): item is string => typeof item === 'string' && Boolean(item)) : []
}

function entryMatchesKeyword(entry: AiwikiWikiEntry, keyword: string) {
  return `${entry.title}\n${entry.excerpt}\n${entry.body_markdown}`.includes(keyword)
}

function applyNodePhysicsAttributes(graph: KnowledgeGraphModel) {
  graph.forEachNode((node, attrs) => {
    const degree = graph.degree(node)
    const base = radiusForKind(attrs.kind)
    const degreeBoost = Math.sqrt(Math.max(0, degree)) * (attrs.kind === 'entry' ? 2.5 : 1.7)
    const radius = Math.min(base + degreeBoost, attrs.kind === 'home' ? 34 : 28)
    graph.mergeNodeAttributes(node, {
      chargeStrength: -(90 + degree * 34 + radius * 8),
      degree,
      neighborIds: graph.neighbors(node),
      radius,
      size: radius,
    })
  })
}

function truncate(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value
}

function seeded(value: string, salt: number) {
  let hash = salt + 17
  for (const char of value) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return (hash % 1000) / 1000
}
