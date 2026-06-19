import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceRadial,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import type { KnowledgeGraphModel } from './graphData'

export interface PhysicsNode extends SimulationNodeDatum {
  id: string
  chargeStrength: number
  radius: number
}

type PhysicsLink = SimulationLinkDatum<PhysicsNode>

export type KnowledgeGraphSimulation = Simulation<PhysicsNode, PhysicsLink>

export function createKnowledgeGraphSimulation(
  graph: KnowledgeGraphModel,
  onTick: () => void,
): KnowledgeGraphSimulation {
  const nodes: PhysicsNode[] = graph.mapNodes((id, attrs) => ({
    id,
    chargeStrength: attrs.chargeStrength,
    radius: attrs.radius,
    x: attrs.x,
    y: attrs.y,
  }))
  const links: PhysicsLink[] = graph.mapEdges((_, __, source, target) => ({
    source,
    target,
  }))

  const simulation = forceSimulation<PhysicsNode>(nodes)
    .alpha(1)
    .alphaDecay(0.018)
    .alphaMin(0.015)
    .velocityDecay(0.34)
    .force('charge', forceManyBody<PhysicsNode>().strength((node) => node.chargeStrength))
    .force('center', forceCenter<PhysicsNode>(0, 0).strength(0.075))
    .force('radial', forceRadial<PhysicsNode>(160, 0, 0).strength(0.025))
    .force('collide', forceCollide<PhysicsNode>().radius((node) => node.radius + 12).strength(0.9).iterations(2))
    .force(
      'link',
      forceLink<PhysicsNode, PhysicsLink>(links)
        .id((node) => node.id)
        .distance((link) => linkDistance(graph, nodeIdOf(link.source), nodeIdOf(link.target)))
        .strength(0.18),
    )
    .on('tick', () => {
      nodes.forEach((node) => {
        graph.mergeNodeAttributes(node.id, {
          x: node.x ?? 0,
          y: node.y ?? 0,
        })
      })
      onTick()
    })

  return simulation
}

export function findPhysicsNode(simulation: KnowledgeGraphSimulation, id: string) {
  return simulation.nodes().find((node) => node.id === id)
}

function nodeIdOf(value: string | number | PhysicsNode): string {
  return typeof value === 'object' ? value.id : String(value)
}

function linkDistance(graph: KnowledgeGraphModel, source: string, target: string) {
  const sourceRadius = graph.getNodeAttribute(source, 'radius')
  const targetRadius = graph.getNodeAttribute(target, 'radius')
  return Math.max(72, sourceRadius + targetRadius + 42)
}
