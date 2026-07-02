import { useEffect, useMemo, useRef } from 'react'
import Sigma from 'sigma'
import type { NodeHoverDrawingFunction } from 'sigma/rendering'
import { Empty, Flex, Space, Tag, Typography, theme } from 'antd'
import type { AiwikiResult } from '../../lib/aiwiki'
import { buildKnowledgeGraph, type KnowledgeGraphNodeAttributes } from './graphData'
import { createKnowledgeGraphSimulation, findPhysicsNode } from './graphLayout'
import { GRAPH_KIND_COLORS } from './graphStyles'

interface KnowledgeGraphProps {
  result: AiwikiResult
  onOpenEntry: (slug: string) => void
}

function roundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  const safeRadius = Math.min(radius, width / 2, height / 2)
  context.beginPath()
  context.moveTo(x + safeRadius, y)
  context.lineTo(x + width - safeRadius, y)
  context.quadraticCurveTo(x + width, y, x + width, y + safeRadius)
  context.lineTo(x + width, y + height - safeRadius)
  context.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height)
  context.lineTo(x + safeRadius, y + height)
  context.quadraticCurveTo(x, y + height, x, y + height - safeRadius)
  context.lineTo(x, y + safeRadius)
  context.quadraticCurveTo(x, y, x + safeRadius, y)
  context.closePath()
}

function createGraphNodeHoverRenderer(colors: {
  chipBackground: string
  chipBorder: string
  labelText: string
  nodeHalo: string
}): NodeHoverDrawingFunction<KnowledgeGraphNodeAttributes> {
  return (context, data, settings) => {
    const label =
      typeof data.hoverLabel === 'string'
        ? data.hoverLabel
        : typeof data.label === 'string'
          ? data.label
          : ''
    const fontSize = settings.labelSize
    const paddingX = 8
    const paddingY = 4
    const chipGap = 6
    const chipHeight = fontSize + paddingY * 2
    const chipRadius = 5
    const haloRadius = data.size + 5

    context.save()
    context.font = `${settings.labelWeight} ${fontSize}px ${settings.labelFont}`
    context.textBaseline = 'middle'

    context.fillStyle = colors.nodeHalo
    context.strokeStyle = colors.chipBorder
    context.lineWidth = 1
    context.beginPath()
    context.arc(data.x, data.y, haloRadius, 0, Math.PI * 2)
    context.fill()
    context.stroke()

    if (label) {
      const textWidth = context.measureText(label).width
      const chipWidth = Math.ceil(textWidth + paddingX * 2)
      const chipX = data.x + haloRadius + chipGap
      const chipY = data.y - chipHeight / 2

      context.shadowOffsetX = 0
      context.shadowOffsetY = 2
      context.shadowBlur = 8
      context.shadowColor = 'rgba(0, 0, 0, 0.34)'
      context.fillStyle = colors.chipBackground
      roundedRect(context, chipX, chipY, chipWidth, chipHeight, chipRadius)
      context.fill()

      context.shadowBlur = 0
      context.strokeStyle = colors.chipBorder
      context.stroke()

      context.fillStyle = colors.labelText
      context.fillText(label, chipX + paddingX, data.y)
    }

    context.restore()
  }
}

export default function KnowledgeGraph({ result, onOpenEntry }: KnowledgeGraphProps) {
  const { token } = theme.useToken()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const hoveredNodeRef = useRef<string | null>(null)
  const { graph, entryCount } = useMemo(() => {
    const model = buildKnowledgeGraph(result)
    return model
  }, [result])
  const drawGraphNodeHover = useMemo(
    () =>
      createGraphNodeHoverRenderer({
        chipBackground: token.colorBgElevated,
        chipBorder: token.colorBorderSecondary,
        labelText: token.colorText,
        nodeHalo: token.colorBgContainer,
      }),
    [token.colorBgContainer, token.colorBgElevated, token.colorBorderSecondary, token.colorText],
  )

  useEffect(() => {
    const container = containerRef.current
    if (!container || !entryCount) return undefined

    let draggedNode: string | null = null
    let isDragging = false
    const highlightedNodes = new Set<string>()
    const renderer = new Sigma(graph, container, {
      allowInvalidContainer: true,
      defaultEdgeColor: '#cbd5e1',
      defaultEdgeType: 'line',
      defaultNodeColor: '#0891b2',
      defaultDrawNodeHover: drawGraphNodeHover,
      edgeReducer: (_, data) => ({ ...data, hidden: false }),
      enableEdgeEvents: false,
      hideEdgesOnMove: false,
      hideLabelsOnMove: true,
      itemSizesReference: 'positions',
      labelColor: { color: token.colorText },
      labelRenderedSizeThreshold: 16,
      labelSize: 12,
      minCameraRatio: 0.15,
      maxCameraRatio: 3,
      nodeReducer: (node, data) => {
        const attrs = data as KnowledgeGraphNodeAttributes
        const active = node === hoveredNodeRef.current
        const related = highlightedNodes.has(node)
        const highlighted = active || related
        return {
          ...attrs,
          label: highlighted ? null : attrs.label,
          hoverLabel: attrs.label,
          forceLabel: !highlighted && Boolean(attrs.forceLabel),
          highlighted,
          size: active ? attrs.size * 1.45 : related ? attrs.size * 1.18 : attrs.size,
          zIndex: active ? 3 : related ? 2 : attrs.kind === 'entry' ? 1 : 0,
        }
      },
      renderLabels: true,
      zIndex: true,
    })
    const simulation = createKnowledgeGraphSimulation(graph, () => {
      renderer.refresh({ skipIndexation: false })
    })

    renderer.on('enterNode', ({ node }) => {
      hoveredNodeRef.current = node
      highlightedNodes.clear()
      highlightedNodes.add(node)
      const attrs = graph.getNodeAttributes(node) as KnowledgeGraphNodeAttributes
      attrs.neighborIds.forEach((neighbor) => highlightedNodes.add(neighbor))
      renderer.refresh()
    })
    renderer.on('leaveNode', () => {
      hoveredNodeRef.current = null
      highlightedNodes.clear()
      renderer.refresh()
    })
    renderer.on('clickNode', ({ node }) => {
      const attrs = graph.getNodeAttributes(node) as KnowledgeGraphNodeAttributes
      if (attrs.kind === 'entry' && attrs.entrySlug) onOpenEntry(attrs.entrySlug)
    })
    renderer.on('downNode', ({ node, event }) => {
      draggedNode = node
      isDragging = true
      const physicsNode = findPhysicsNode(simulation, node)
      if (physicsNode) {
        physicsNode.fx = physicsNode.x
        physicsNode.fy = physicsNode.y
      }
      event.preventSigmaDefault()
      if (!renderer.getCustomBBox()) renderer.setCustomBBox(renderer.getBBox())
    })

    const mouseCaptor = renderer.getMouseCaptor()
    mouseCaptor.on('mousemovebody', (event) => {
      if (!isDragging || !draggedNode) return
      const position = renderer.viewportToGraph(event)
      graph.setNodeAttribute(draggedNode, 'x', position.x)
      graph.setNodeAttribute(draggedNode, 'y', position.y)
      const physicsNode = findPhysicsNode(simulation, draggedNode)
      if (physicsNode) {
        physicsNode.fx = position.x
        physicsNode.fy = position.y
      }
      event.preventSigmaDefault()
      event.original.preventDefault()
      renderer.refresh({ skipIndexation: false })
    })
    mouseCaptor.on('mouseup', () => {
      if (draggedNode) {
        const physicsNode = findPhysicsNode(simulation, draggedNode)
        if (physicsNode) {
          physicsNode.fx = null
          physicsNode.fy = null
        }
      }
      draggedNode = null
      isDragging = false
      simulation.alphaTarget(0.08).restart()
      window.setTimeout(() => simulation.alphaTarget(0.015), 600)
    })
    mouseCaptor.on('mouseleave', () => {
      if (draggedNode) {
        const physicsNode = findPhysicsNode(simulation, draggedNode)
        if (physicsNode) {
          physicsNode.fx = null
          physicsNode.fy = null
        }
      }
      draggedNode = null
      isDragging = false
      simulation.alphaTarget(0.08).restart()
      window.setTimeout(() => simulation.alphaTarget(0.015), 600)
    })

    return () => {
      simulation.stop()
      renderer.kill()
    }
  }, [drawGraphNodeHover, entryCount, graph, onOpenEntry, token.colorText])

  if (!entryCount) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可展示的词条关系" />
  }

  return (
    <Flex vertical gap={14}>
      <div
        ref={containerRef}
        style={{
          height: 640,
          border: `1px solid ${token.colorBorderSecondary}`,
          borderRadius: 8,
          overflow: 'hidden',
          background: token.colorBgElevated,
        }}
      />
      <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
        <Typography.Text type="secondary">
          {entryCount} 个词条，{graph.order} 个节点，{graph.size} 条关系。节点可拖拽，悬停显示标题，点击词条圆点打开详情。
        </Typography.Text>
        <Space wrap>
          <Tag color={GRAPH_KIND_COLORS.entry}>词条</Tag>
          <Tag color={GRAPH_KIND_COLORS.type}>分类</Tag>
          <Tag color={GRAPH_KIND_COLORS.tag}>标签</Tag>
          <Tag color={GRAPH_KIND_COLORS.keyword}>关键词</Tag>
        </Space>
      </Flex>
    </Flex>
  )
}
