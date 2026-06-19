import type { GraphKind } from './graphData'

export const GRAPH_KIND_COLORS: Record<GraphKind, string> = {
  home: '#4f46e5',
  entry: '#0891b2',
  type: '#7c3aed',
  tag: '#d97706',
  keyword: '#16a34a',
}

export const ENTRY_TYPE_COLORS: Record<string, string> = {
  hotspot: '#dc2626',
  pain_point: '#ea580c',
  solution: '#16a34a',
  topic: '#2563eb',
  search_intent: '#9333ea',
  article: '#0d9488',
}

export function radiusForKind(kind: GraphKind) {
  if (kind === 'home') return 18
  if (kind === 'entry') return 13
  if (kind === 'type') return 10
  return 8
}

export function colorForKind(kind: GraphKind, entryType?: string) {
  return entryType ? ENTRY_TYPE_COLORS[entryType] ?? GRAPH_KIND_COLORS.entry : GRAPH_KIND_COLORS[kind]
}
