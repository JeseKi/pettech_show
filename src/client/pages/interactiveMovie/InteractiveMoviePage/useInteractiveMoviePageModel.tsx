import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent, PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react'
import { App, Input } from 'antd'
import { closeInteractiveMoviePublication, createInteractiveMovieProject, deleteInteractiveMovieProject, getInteractiveMovieProject, getInteractiveMoviePromptTemplate, getInteractiveMovieSyncState, listInteractiveMovieReleases, listInteractiveMovieProjects, patchInteractiveMovieProject, publishInteractiveMovieProject, renameInteractiveMovieProject, setInteractiveMoviePublishedRelease, uploadInteractiveMovieImage, uploadInteractiveMovieVideo } from '../../../lib/interactiveMovie'
import type { InteractiveMovieProjectDetail, InteractiveMovieRelease, PromptTemplate } from '../../../lib/interactiveMovie'
import { resolveErrorMessage } from '../../../lib/errorMessage'
import type { AssetNode, AssetNodeType, AssetUploadState, CanvasContextMenuState, CanvasViewport, ChoiceEdge, ConnectableNodeType, InteractionState, InteractiveMovieProject, LinkDraftState, NodeHandleSide, NodeLink, NodeLinkEndpoint, SceneNode, SelectedObject, StoredWorkspace } from '../interactiveMovieTypes'
import { LINK_SNAP_RADIUS, MAX_ZOOM, MIN_ZOOM, NODE_WIDTH, clamp, uniqueId } from '../interactiveMovieConstants'
import { createDefaultProject, createDraftAssetNode, createDraftScene, firstSelectableObject, normalizeProjectChoices } from '../interactiveMovieProject'
import { cleanupProjectReplicasOutside, cloudReplicaKey, draftReplicaKey, hasCloudCopy, isMissingCloudProjectError, loadScenePanelState, loadWorkspace, persistScenePanelState, persistWorkspaceLocally, readProjectReplica, removeProjectReplicas, withCloudMeta, writeProjectReplica } from '../interactiveMovieStorage'
import { buildProjectPatch, localDraftIsNewer, mergeDraftWithCloudMeta, patchHasChanges } from '../interactiveMoviePatch'
import { getScenePosterUrl, getSceneVideoUrl, handleAnchor, nodeBounds, nodeDimensions, projectHasNodePairLink, resolveFloatingEndpoint, sameNodeEndpoint } from '../interactiveMovieCanvas'

export function useInteractiveMoviePageModel() {
  const { message, modal } = App.useApp()
  const canvasRef = useRef<HTMLDivElement>(null)
  const interactionRef = useRef<InteractionState | null>(null)
  const lastCanvasSceneIdByProjectRef = useRef<Record<string, string>>({})

  const [workspace, setWorkspace] = useState<StoredWorkspace>(() => loadWorkspace())
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false)
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false)
  const [bottomToolbarCollapsed, setBottomToolbarCollapsed] = useState(false)
  const [promptTemplate, setPromptTemplate] = useState<PromptTemplate | null>(null)
  const [uploadByAssetId, setUploadByAssetId] = useState<Record<string, AssetUploadState>>({})
  const [cloudReady, setCloudReady] = useState(false)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState('本地草稿')
  const [publishModalOpen, setPublishModalOpen] = useState(false)
  const [releaseHistory, setReleaseHistory] = useState<InteractiveMovieRelease[]>([])
  const [releaseLoading, setReleaseLoading] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewSceneId, setPreviewSceneId] = useState('')
  const [previewLineIndex, setPreviewLineIndex] = useState(0)
  const [previewChoicesVisible, setPreviewChoicesVisible] = useState(false)
  const [canvasContextMenu, setCanvasContextMenu] = useState<CanvasContextMenuState | null>(null)
  const [linkDraft, setLinkDraft] = useState<LinkDraftState | null>(null)
  const linkDraftRef = useRef<LinkDraftState | null>(null)
  const [scenePanelState, setScenePanelState] = useState<Record<string, string[]>>(() => loadScenePanelState())

  const activeProject = workspace.projects.find((project) => project.id === workspace.activeProjectId) ?? workspace.projects[0]
  const scenes = activeProject.scenes
  const choices = activeProject.choices
  const assetNodes = activeProject.assetNodes
  const nodeLinks = activeProject.nodeLinks
  const selectedObject = activeProject.selectedObject
  const viewport = activeProject.viewport

  const selectedScene = selectedObject.type === 'scene'
    ? scenes.find((scene) => scene.id === selectedObject.id) ?? null
    : null
  const selectedChoice = selectedObject.type === 'choice'
    ? choices.find((choice) => choice.id === selectedObject.id) ?? null
    : null
  const selectedAsset = selectedObject.type !== 'scene' && selectedObject.type !== 'choice'
    && selectedObject.type !== 'nodeLink'
    ? assetNodes.find((asset) => asset.id === selectedObject.id) ?? null
    : null
  const selectedNodeLink = selectedObject.type === 'nodeLink'
    ? nodeLinks.find((link) => link.id === selectedObject.id) ?? null
    : null
  const sceneMap = useMemo(() => new Map(scenes.map((scene) => [scene.id, scene])), [scenes])
  const assetMap = useMemo(() => new Map(assetNodes.map((asset) => [asset.id, asset])), [assetNodes])
  const videoNodes = useMemo(() => assetNodes.filter((asset) => asset.type === 'video'), [assetNodes])
  const imageNodes = useMemo(() => assetNodes.filter((asset) => asset.type === 'image'), [assetNodes])
  const startScene = scenes.find((scene) => scene.role === 'start') ?? scenes[0]
  const previewScene = scenes.find((scene) => scene.id === previewSceneId) ?? startScene
  const outgoingPreviewChoices = choices.filter((choice) => (
    choice.fromSceneId === previewScene?.id && sceneMap.has(choice.toSceneId)
  ))
  const previewVideoUrl = getSceneVideoUrl(previewScene, assetMap)
  const previewPosterUrl = getScenePosterUrl(previewScene, assetMap)
  const previewHasVideo = Boolean(previewVideoUrl)
  const currentPreviewLine = previewScene?.script.lines[previewLineIndex]
  const activeProjectCloudBase = hasCloudCopy(activeProject) ? readProjectReplica(cloudReplicaKey(activeProject.id)) : null
  const activeProjectHasUnsavedChanges = !activeProjectCloudBase
    || patchHasChanges(buildProjectPatch(activeProjectCloudBase, activeProject))
  const activeProjectPublicPath = activeProject.publicPath ?? `/interactive-movie/play/${activeProject.id}`
  const activeProjectPublicUrl = typeof window === 'undefined'
    ? activeProjectPublicPath
    : `${window.location.origin}${activeProjectPublicPath}`

  const updateLinkDraftState = (draft: LinkDraftState | null) => {
    linkDraftRef.current = draft
    setLinkDraft(draft)
  }

  useEffect(() => {
    persistWorkspaceLocally(workspace)
  }, [workspace])

  useEffect(() => {
    persistScenePanelState(scenePanelState)
  }, [scenePanelState])

  useEffect(() => {
    let cancelled = false
    const loadCloudWorkspace = async () => {
      try {
        const summaries = await listInteractiveMovieProjects()
        if (cancelled) return
        if (summaries.length === 0) {
          const localProject = workspace.projects.find((project) => !hasCloudCopy(project))
          if (!localProject) {
            const project = createDefaultProject('互动电影草稿')
            cleanupProjectReplicasOutside(new Set([project.id]))
            writeProjectReplica(draftReplicaKey(project.id), project)
            setWorkspace({ activeProjectId: project.id, projects: [project] })
            setSyncMessage('云端暂无项目')
            return
          }
          cleanupProjectReplicasOutside(new Set([localProject.id]))
          const created = await createInteractiveMovieProject(localProject.title, localProject)
          if (cancelled) return
          const project = withCloudMeta(created)
          cleanupProjectReplicasOutside(new Set([project.id]))
          writeProjectReplica(cloudReplicaKey(project.id), project)
          writeProjectReplica(draftReplicaKey(project.id), project)
          setWorkspace({ activeProjectId: project.id, projects: [project] })
          setSyncMessage('已连接云端')
          return
        }
        const detailResults = await Promise.all(summaries.map(async (summary) => {
          try {
            return await getInteractiveMovieProject<InteractiveMovieProject>(summary.id)
          } catch (error) {
            if (isMissingCloudProjectError(error)) {
              removeProjectReplicas(summary.id)
              return null
            }
            throw error
          }
        }))
        if (cancelled) return
        const details = detailResults.filter((detail): detail is InteractiveMovieProjectDetail<InteractiveMovieProject> => detail !== null)
        if (details.length === 0) {
          const project = createDefaultProject('互动电影草稿')
          cleanupProjectReplicasOutside(new Set([project.id]))
          writeProjectReplica(draftReplicaKey(project.id), project)
          setWorkspace({ activeProjectId: project.id, projects: [project] })
          setSyncMessage('云端暂无项目')
          return
        }
        const projects = details.map((detail) => {
          const cloudProject = withCloudMeta(detail)
          writeProjectReplica(cloudReplicaKey(cloudProject.id), cloudProject)
          const draftProject = readProjectReplica(draftReplicaKey(cloudProject.id))
          if (draftProject) {
            const hasLocalChanges = patchHasChanges(buildProjectPatch(cloudProject, draftProject))
            if (hasLocalChanges && localDraftIsNewer(draftProject, cloudProject)) {
              return mergeDraftWithCloudMeta(draftProject, cloudProject)
            }
          }
          writeProjectReplica(draftReplicaKey(cloudProject.id), cloudProject)
          return cloudProject
        })
        cleanupProjectReplicasOutside(new Set(projects.map((project) => project.id)))
        const activeId = projects.some((project) => project.id === workspace.activeProjectId)
          ? workspace.activeProjectId
          : projects[0].id
        setWorkspace({ activeProjectId: activeId, projects })
        setSyncMessage('已连接云端')
      } catch (error) {
        setSyncMessage(resolveErrorMessage(error))
      } finally {
        if (!cancelled) setCloudReady(true)
      }
    }
    void loadCloudWorkspace()
    return () => {
      cancelled = true
    }
    // only bootstrap once from the best local snapshot available at mount time
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setWorkspace((current) => {
      const normalizedProjects = current.projects.map(normalizeProjectChoices)
      const changed = normalizedProjects.some((project, index) => project.choices.length !== current.projects[index].choices.length
        || project.choices.some((choice, choiceIndex) => choice.toSceneId !== current.projects[index].choices[choiceIndex]?.toSceneId))
      return changed ? { ...current, projects: normalizedProjects } : current
    })
  }, [])

  useEffect(() => {
    void getInteractiveMoviePromptTemplate()
      .then(setPromptTemplate)
      .catch(() => {
        setPromptTemplate(null)
      })
  }, [])

  const updateActiveProject = useCallback((updater: (project: InteractiveMovieProject) => InteractiveMovieProject) => {
    setWorkspace((current) => ({
      ...current,
      projects: current.projects.map((project) => (
        project.id === current.activeProjectId
          ? { ...updater(project), updatedAt: new Date().toISOString() }
          : project
      )),
    }))
  }, [])

  const updateScene = (sceneId: string, updater: (scene: SceneNode) => SceneNode) => {
    updateActiveProject((project) => ({
      ...project,
      scenes: project.scenes.map((scene) => (scene.id === sceneId ? updater(scene) : scene)),
    }))
  }

  const updateAsset = (assetId: string, updater: (asset: AssetNode) => AssetNode) => {
    updateActiveProject((project) => ({
      ...project,
      assetNodes: project.assetNodes.map((asset) => (asset.id === assetId ? updater(asset) : asset)),
    }))
  }

  const updateChoice = (choiceId: string, updater: (choice: ChoiceEdge) => ChoiceEdge) => {
    updateActiveProject((project) => ({
      ...project,
      choices: project.choices.map((choice) => (choice.id === choiceId ? updater(choice) : choice)),
    }))
  }

  const setSelectedObject = (nextSelectedObject: SelectedObject) => {
    updateActiveProject((project) => ({ ...project, selectedObject: nextSelectedObject }))
  }

  const replaceProjectFromServer = (detail: InteractiveMovieProjectDetail<InteractiveMovieProject>) => {
    const project = withCloudMeta(detail)
    writeProjectReplica(cloudReplicaKey(project.id), project)
    writeProjectReplica(draftReplicaKey(project.id), project)
    setWorkspace((current) => ({
      ...current,
      activeProjectId: current.activeProjectId === detail.id ? project.id : current.activeProjectId,
      projects: current.projects.map((item) => (item.id === project.id ? project : item)),
    }))
    return project
  }

  const selectCanvasScene = (sceneId: string) => {
    lastCanvasSceneIdByProjectRef.current[activeProject.id] = sceneId
    setSelectedObject({ type: 'scene', id: sceneId })
  }

  const setViewport = (nextViewport: CanvasViewport | ((current: CanvasViewport) => CanvasViewport)) => {
    updateActiveProject((project) => ({
      ...project,
      viewport: typeof nextViewport === 'function' ? nextViewport(project.viewport) : nextViewport,
    }))
  }

  const createProject = () => {
    const project = createDefaultProject(`互动电影 ${workspace.projects.length + 1}`)
    writeProjectReplica(draftReplicaKey(project.id), project)
    setWorkspace((current) => ({
      activeProjectId: project.id,
      projects: [project, ...current.projects],
    }))
    setSyncMessage('新项目未保存')
    message.success('已创建新项目')
  }

  const switchProject = (projectId: string) => {
    setWorkspace((current) => ({ ...current, activeProjectId: projectId }))
  }

  const cleanupMissingCloudProject = useCallback((projectId: string) => {
    removeProjectReplicas(projectId)
    setWorkspace((current) => {
      const remaining = current.projects.filter((item) => item.id !== projectId)
      if (remaining.length > 0) {
        const nextActiveId = current.activeProjectId === projectId ? remaining[0].id : current.activeProjectId
        return { activeProjectId: nextActiveId, projects: remaining }
      }
      const nextProject = createDefaultProject('互动电影草稿')
      writeProjectReplica(draftReplicaKey(nextProject.id), nextProject)
      return { activeProjectId: nextProject.id, projects: [nextProject] }
    })
    setSyncMessage('云端项目不存在，已清理本地副本')
  }, [])

  const confirmDeleteProject = (project: InteractiveMovieProject) => {
    modal.confirm({
      title: `删除项目「${project.title}」？`,
      content: '此操作无法撤回。项目会从云端和本地草稿中删除。',
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          if (hasCloudCopy(project)) {
            await deleteInteractiveMovieProject(project.id)
          }
          removeProjectReplicas(project.id)
          setWorkspace((current) => {
            const remaining = current.projects.filter((item) => item.id !== project.id)
            if (remaining.length > 0) {
              const nextActiveId = current.activeProjectId === project.id ? remaining[0].id : current.activeProjectId
              return { activeProjectId: nextActiveId, projects: remaining }
            }
            const nextProject = createDefaultProject('互动电影草稿')
            writeProjectReplica(draftReplicaKey(nextProject.id), nextProject)
            return { activeProjectId: nextProject.id, projects: [nextProject] }
          })
          setSyncMessage('项目已删除')
          message.success('项目已删除')
        } catch (error) {
          if (isMissingCloudProjectError(error)) {
            cleanupMissingCloudProject(project.id)
            message.warning('云端项目不存在，已清理本地副本')
            return
          }
          message.error(resolveErrorMessage(error))
          throw error
        }
      },
    })
  }

  const confirmRenameProject = (project: InteractiveMovieProject) => {
    let nextTitle = project.title
    modal.confirm({
      title: `重命名项目「${project.title}」`,
      content: (
        <Input
          autoFocus
          defaultValue={project.title}
          maxLength={80}
          onChange={(event) => {
            nextTitle = event.target.value
          }}
          placeholder="输入项目名称"
        />
      ),
      okText: '保存',
      cancelText: '取消',
      async onOk() {
        const title = nextTitle.trim()
        if (!title) {
          message.warning('项目名称不能为空')
          throw new Error('项目名称不能为空')
        }

        try {
          const hasCloudCopy = Boolean(project.version && project.contentHash)
          if (hasCloudCopy) {
            const renamed = await renameInteractiveMovieProject<InteractiveMovieProject>(project.id, title)
            const nextProject = withCloudMeta(renamed)
            writeProjectReplica(cloudReplicaKey(nextProject.id), nextProject)
            writeProjectReplica(draftReplicaKey(nextProject.id), nextProject)
            setWorkspace((current) => ({
              ...current,
              projects: current.projects.map((item) => (item.id === nextProject.id ? nextProject : item)),
            }))
            setSyncMessage('项目已重命名')
            message.success('项目已重命名')
            return
          }

          const nextProject = { ...project, title, updatedAt: new Date().toISOString() }
          writeProjectReplica(draftReplicaKey(nextProject.id), nextProject)
          setWorkspace((current) => ({
            ...current,
            projects: current.projects.map((item) => (item.id === nextProject.id ? nextProject : item)),
          }))
          setSyncMessage('本地草稿已重命名')
          message.success('项目已重命名')
        } catch (error) {
          message.error(resolveErrorMessage(error))
          throw error
        }
      },
    })
  }

  const renameProject = (title: string) => {
    updateActiveProject((project) => ({ ...project, title }))
  }

  const beginPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    setCanvasContextMenu(null)
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'pan',
      pointerId: event.pointerId,
      startClient: { x: event.clientX, y: event.clientY },
      startViewport: viewport,
    }
  }

  const beginNodeDrag = (event: ReactPointerEvent<HTMLDivElement>, nodeType: 'scene' | AssetNodeType, nodeId: string) => {
    if (event.button !== 0) return
    event.stopPropagation()
    const node = nodeType === 'scene'
      ? scenes.find((item) => item.id === nodeId)
      : assetNodes.find((item) => item.id === nodeId)
    if (!node) return
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'node',
      pointerId: event.pointerId,
      nodeType,
      nodeId,
      startClient: { x: event.clientX, y: event.clientY },
      startPosition: node.position,
    }
    setSelectedObject({ type: nodeType, id: nodeId })
  }

  const beginChoiceDrag = (event: ReactPointerEvent<HTMLButtonElement>, choiceId: string) => {
    if (event.button !== 0) return
    event.stopPropagation()
    const choice = choices.find((item) => item.id === choiceId)
    if (!choice) return
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'choice',
      pointerId: event.pointerId,
      choiceId,
      startClient: { x: event.clientX, y: event.clientY },
      startOffsetX: choice.offsetX ?? 0,
      startOffsetY: choice.offsetY ?? 0,
    }
    setSelectedObject({ type: 'choice', id: choiceId })
  }

  const canvasPointFromEvent = (event: { clientX: number; clientY: number }) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return {
      x: (event.clientX - rect.left - viewport.x) / viewport.zoom,
      y: (event.clientY - rect.top - viewport.y) / viewport.zoom,
    }
  }

  const snapEndpointFromCanvasPoint = (
    point: { x: number; y: number },
    exclude?: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  ): NodeLinkEndpoint | null => {
    const radius = LINK_SNAP_RADIUS / viewport.zoom
    const candidates: Array<Pick<NodeLinkEndpoint, 'type' | 'id'>> = [
      ...scenes.map((scene) => ({ type: 'scene' as const, id: scene.id })),
      ...assetNodes.map((asset) => ({ type: asset.type, id: asset.id })),
    ]
    let bestEndpoint: NodeLinkEndpoint | null = null
    let bestDistance = Number.POSITIVE_INFINITY
    for (const candidate of candidates) {
      if (exclude && sameNodeEndpoint(candidate, exclude)) continue
      const bounds = nodeBounds(candidate, sceneMap, assetMap)
      if (!bounds) continue
      const insideExpandedBounds = (
        point.x >= bounds.x - radius
        && point.x <= bounds.x + bounds.width + radius
        && point.y >= bounds.y - radius
        && point.y <= bounds.y + bounds.height + radius
      )
      const dx = point.x - bounds.centerX
      const dy = point.y - bounds.centerY
      const side: NodeHandleSide = Math.abs(dx) / bounds.width >= Math.abs(dy) / bounds.height
        ? (dx >= 0 ? 'right' : 'left')
        : (dy >= 0 ? 'bottom' : 'top')
      const endpoint = { ...candidate, handle: side }
      const anchor = handleAnchor(endpoint, sceneMap, assetMap)
      if (!anchor) continue
      const distance = Math.hypot(point.x - anchor.x, point.y - anchor.y)
      if (!insideExpandedBounds && distance > radius) continue
      if (distance < bestDistance) {
        bestEndpoint = endpoint
        bestDistance = distance
      }
    }
    return bestEndpoint
  }

  const draftPoint = (
    point: { x: number; y: number },
    exclude?: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  ) => {
    const target = snapEndpointFromCanvasPoint(point, exclude)
    if (!target) return { current: point, target: undefined }
    return {
      current: handleAnchor(target, sceneMap, assetMap) ?? point,
      target,
    }
  }

  const beginLinkDrag = (
    event: ReactPointerEvent<HTMLButtonElement>,
    endpoint: NodeLinkEndpoint,
  ) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'link',
      pointerId: event.pointerId,
      source: endpoint,
    }
    const point = canvasPointFromEvent(event)
    const snap = draftPoint(point, endpoint)
    updateLinkDraftState({ mode: 'create', source: endpoint, current: snap.current, target: snap.target })
    setSelectedObject({ type: endpoint.type, id: endpoint.id })
  }

  const beginNodeLinkRouteDrag = (
    event: ReactPointerEvent<SVGPathElement>,
    link: NodeLink,
  ) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'nodeLink',
      pointerId: event.pointerId,
      linkId: link.id,
      startClient: { x: event.clientX, y: event.clientY },
      startOffsetX: link.offsetX ?? 0,
      startOffsetY: link.offsetY ?? 0,
    }
    setSelectedObject({ type: 'nodeLink', id: link.id })
  }

  const beginNodeLinkEndpointDrag = (
    event: ReactPointerEvent<SVGPathElement | SVGCircleElement | HTMLButtonElement>,
    link: NodeLink,
    activeEnd: 'from' | 'to',
  ) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    const point = canvasPointFromEvent(event)
    interactionRef.current = {
      type: 'nodeLinkEndpoint',
      pointerId: event.pointerId,
      linkId: link.id,
      activeEnd,
    }
    setSelectedObject({ type: 'nodeLink', id: link.id })
    const fixedEndpoint = activeEnd === 'from' ? link.to : link.from
    const snap = draftPoint(point, fixedEndpoint)
    updateLinkDraftState({
      mode: 'reconnect',
      linkId: link.id,
      activeEnd,
      fixedEndpoint,
      current: snap.current,
      target: snap.target,
    })
  }

  const completeLinkDrag = (target: NodeLinkEndpoint) => {
    const draft = linkDraftRef.current
    if (!draft) return
    const rawFrom = draft.mode === 'create'
      ? draft.source
      : draft.activeEnd === 'from'
        ? target
        : draft.fixedEndpoint
    const rawTo = draft.mode === 'create'
      ? target
      : draft.activeEnd === 'to'
        ? target
        : draft.fixedEndpoint
    if (sameNodeEndpoint(rawFrom, rawTo)) {
      interactionRef.current = null
      updateLinkDraftState(null)
      return
    }
    const nextFrom = resolveFloatingEndpoint(rawFrom, rawTo, sceneMap, assetMap)
    const nextTo = resolveFloatingEndpoint(rawTo, rawFrom, sceneMap, assetMap)
    const linkId = draft.mode === 'create' ? uniqueId('link') : draft.linkId
    let rejectedDuplicate = false
    updateActiveProject((project) => {
      if (projectHasNodePairLink(project, nextFrom, nextTo, draft.mode === 'reconnect' ? draft.linkId : '')) {
        rejectedDuplicate = true
        return project
      }
      if (draft.mode === 'reconnect') {
        return {
          ...project,
          nodeLinks: project.nodeLinks.map((link) => (
            link.id === draft.linkId ? { ...link, from: nextFrom, to: nextTo } : link
          )),
          selectedObject: { type: 'nodeLink', id: draft.linkId },
        }
      }
      return {
        ...project,
        nodeLinks: [...project.nodeLinks, { id: linkId, from: nextFrom, to: nextTo }],
        selectedObject: { type: 'nodeLink', id: linkId },
      }
    })
    if (rejectedDuplicate) message.warning('这两个节点之间已经存在连接')
    interactionRef.current = null
    updateLinkDraftState(null)
  }

  const linkEndpointFromPoint = (event: ReactPointerEvent<HTMLElement>): NodeLinkEndpoint | null => {
    const element = document.elementFromPoint(event.clientX, event.clientY)
    const handle = element?.closest<HTMLButtonElement>('.movie-node-handle')
    const type = handle?.dataset.nodeType as ConnectableNodeType | undefined
    const id = handle?.dataset.nodeId
    const side = handle?.dataset.handle as NodeHandleSide | undefined
    if (type && id && side) return { type, id, handle: side }
    const interaction = interactionRef.current
    const exclude = interaction?.type === 'link'
      ? interaction.source
      : linkDraft?.mode === 'reconnect'
        ? linkDraft.fixedEndpoint
        : undefined
    return snapEndpointFromCanvasPoint(canvasPointFromEvent(event), exclude)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current
    if (!interaction || interaction.pointerId !== event.pointerId) return
    if (interaction.type === 'pan') {
      setViewport({
        ...interaction.startViewport,
        x: interaction.startViewport.x + event.clientX - interaction.startClient.x,
        y: interaction.startViewport.y + event.clientY - interaction.startClient.y,
      })
      return
    }
    if (interaction.type === 'node') {
      const dx = (event.clientX - interaction.startClient.x) / viewport.zoom
      const dy = (event.clientY - interaction.startClient.y) / viewport.zoom
      const nextPosition = {
        x: interaction.startPosition.x + dx,
        y: interaction.startPosition.y + dy,
      }
      if (interaction.nodeType === 'scene') {
        updateScene(interaction.nodeId, (scene) => ({ ...scene, position: nextPosition }))
      } else {
        updateAsset(interaction.nodeId, (asset) => ({ ...asset, position: nextPosition }))
      }
      return
    }
    if (interaction.type === 'link') {
      const point = canvasPointFromEvent(event)
      const snap = draftPoint(point, interaction.source)
      const current = linkDraftRef.current
      updateLinkDraftState(current && current.mode === 'create'
        ? { ...current, current: snap.current, target: snap.target }
        : current)
      return
    }
    if (interaction.type === 'nodeLink') {
      const dx = (event.clientX - interaction.startClient.x) / viewport.zoom
      const dy = (event.clientY - interaction.startClient.y) / viewport.zoom
      updateActiveProject((project) => ({
        ...project,
        nodeLinks: project.nodeLinks.map((link) => (
          link.id === interaction.linkId
            ? { ...link, offsetX: interaction.startOffsetX + dx, offsetY: interaction.startOffsetY + dy }
            : link
        )),
      }))
      return
    }
    if (interaction.type === 'nodeLinkEndpoint') {
      const point = canvasPointFromEvent(event)
      const link = activeProject.nodeLinks.find((item) => item.id === interaction.linkId)
      if (!link) return
      const fixedEndpoint = interaction.activeEnd === 'from' ? link.to : link.from
      const snap = draftPoint(point, fixedEndpoint)
      updateLinkDraftState({
        mode: 'reconnect',
        linkId: link.id,
        activeEnd: interaction.activeEnd,
        fixedEndpoint,
        current: snap.current,
        target: snap.target,
      })
      return
    }
    if (interaction.type === 'choice') {
      const dx = (event.clientX - interaction.startClient.x) / viewport.zoom
      const dy = (event.clientY - interaction.startClient.y) / viewport.zoom
      updateChoice(interaction.choiceId, (choice) => ({
        ...choice,
        offsetX: interaction.startOffsetX + dx,
        offsetY: interaction.startOffsetY + dy,
      }))
    }
  }

  const endPointerInteraction = (event: ReactPointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current
    if (interaction?.pointerId === event.pointerId) {
      if (interaction.type === 'link') {
        const target = linkEndpointFromPoint(event)
        if (target) {
          completeLinkDrag(target)
          return
        }
      }
      if (interaction.type === 'nodeLinkEndpoint') {
        const target = linkEndpointFromPoint(event)
        if (target) {
          completeLinkDrag(target)
          return
        }
      }
      interactionRef.current = null
      updateLinkDraftState(null)
    }
  }

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    setCanvasContextMenu(null)
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const nextZoom = clamp(viewport.zoom - event.deltaY * 0.0012, MIN_ZOOM, MAX_ZOOM)
    const canvasX = (event.clientX - rect.left - viewport.x) / viewport.zoom
    const canvasY = (event.clientY - rect.top - viewport.y) / viewport.zoom
    setViewport({
      x: event.clientX - rect.left - canvasX * nextZoom,
      y: event.clientY - rect.top - canvasY * nextZoom,
      zoom: nextZoom,
    })
  }

  const zoomBy = (delta: number) => {
    setViewport((current) => ({ ...current, zoom: clamp(current.zoom + delta, MIN_ZOOM, MAX_ZOOM) }))
  }

  const fitView = () => {
    const positionedNodes = [...scenes, ...assetNodes]
    if (!canvasRef.current || positionedNodes.length === 0) return
    const rect = canvasRef.current.getBoundingClientRect()
    const minX = Math.min(...positionedNodes.map((node) => node.position.x))
    const minY = Math.min(...positionedNodes.map((node) => node.position.y))
    const maxX = Math.max(...positionedNodes.map((node) => {
      const type = 'role' in node ? 'scene' : node.type
      return node.position.x + nodeDimensions(type).width
    }))
    const maxY = Math.max(...positionedNodes.map((node) => {
      const type = 'role' in node ? 'scene' : node.type
      return node.position.y + nodeDimensions(type).height
    }))
    const contentWidth = maxX - minX
    const contentHeight = maxY - minY
    const zoom = clamp(Math.min((rect.width - 160) / contentWidth, (rect.height - 160) / contentHeight), MIN_ZOOM, 1.2)
    setViewport({
      x: rect.width / 2 - (minX + contentWidth / 2) * zoom,
      y: rect.height / 2 - (minY + contentHeight / 2) * zoom,
      zoom,
    })
  }

  const defaultNewScenePosition = () => ({
    x: (-viewport.x + 260) / viewport.zoom,
    y: (-viewport.y + 180) / viewport.zoom,
  })

  const addScene = (position = defaultNewScenePosition()) => {
    const scene = createDraftScene(`新场景 ${scenes.length + 1}`, position)
    updateActiveProject((project) => ({
      ...project,
      scenes: [...project.scenes, scene],
      selectedObject: { type: 'scene', id: scene.id },
    }))
  }

  const addAssetNode = (type: AssetNodeType, position = defaultNewScenePosition()) => {
    const titlePrefix = type === 'text' ? '文本' : type === 'image' ? '图片' : '视频'
    const count = assetNodes.filter((asset) => asset.type === type).length + 1
    const asset = createDraftAssetNode(type, `${titlePrefix} ${count}`, position)
    updateActiveProject((project) => ({
      ...project,
      assetNodes: [...project.assetNodes, asset],
      selectedObject: { type, id: asset.id },
    }))
  }

  const openCanvasContextMenu = (event: ReactMouseEvent<HTMLDivElement>) => {
    event.preventDefault()
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const menuWidth = 178
    const menuHeight = 210
    setCanvasContextMenu({
      screenX: clamp(event.clientX - rect.left, 8, Math.max(8, rect.width - menuWidth - 8)),
      screenY: clamp(event.clientY - rect.top, 8, Math.max(8, rect.height - menuHeight - 8)),
      canvasPosition: {
        x: (event.clientX - rect.left - viewport.x) / viewport.zoom,
        y: (event.clientY - rect.top - viewport.y) / viewport.zoom,
      },
    })
  }

  const runContextMenuAction = (action: () => void) => {
    action()
    setCanvasContextMenu(null)
  }

  const deleteNodeLink = useCallback((linkId: string) => {
    updateActiveProject((project) => {
      const nextNodeLinks = project.nodeLinks.filter((link) => link.id !== linkId)
      const selectedObjectWasDeleted = project.selectedObject.type === 'nodeLink' && project.selectedObject.id === linkId
      return {
        ...project,
        nodeLinks: nextNodeLinks,
        selectedObject: selectedObjectWasDeleted
          ? firstSelectableObject(project.scenes, project.choices, project.assetNodes)
          : project.selectedObject,
      }
    })
  }, [updateActiveProject])

  const deleteAssetNode = (assetId: string) => {
    updateActiveProject((project) => {
      const deleted = project.assetNodes.find((asset) => asset.id === assetId)
      if (!deleted) return project
      const nextAssets = project.assetNodes.filter((asset) => asset.id !== assetId)
      const removedNodeLinkIds = new Set(
        project.nodeLinks
          .filter((link) => (
            (link.from.id === assetId && link.from.type === deleted.type)
            || (link.to.id === assetId && link.to.type === deleted.type)
          ))
          .map((link) => link.id),
      )
      const nextNodeLinks = project.nodeLinks.filter((link) => !removedNodeLinkIds.has(link.id))
      const selectedObjectWasDeleted = (
        (project.selectedObject.id === assetId && project.selectedObject.type === deleted.type)
        || (project.selectedObject.type === 'nodeLink' && removedNodeLinkIds.has(project.selectedObject.id))
      )
      return {
        ...project,
        assetNodes: nextAssets,
        nodeLinks: nextNodeLinks,
        scenes: project.scenes.map((scene) => ({
          ...scene,
          media: {
            ...scene.media,
            videoNodeId: scene.media.videoNodeId === assetId ? '' : scene.media.videoNodeId,
            coverImageNodeId: scene.media.coverImageNodeId === assetId ? '' : scene.media.coverImageNodeId,
          },
        })),
        selectedObject: selectedObjectWasDeleted
          ? firstSelectableObject(project.scenes, project.choices, nextAssets)
          : project.selectedObject,
      }
    })
  }

  const confirmDeleteAssetNode = (assetId: string) => {
    const asset = assetNodes.find((item) => item.id === assetId)
    if (!asset) return
    modal.confirm({
      title: `删除素材「${asset.title}」？`,
      content: '删除后会从画布中移除这个素材，并清空场景中的关联引用。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk() {
        deleteAssetNode(assetId)
        message.success('素材已删除')
      },
    })
  }

  const createSceneForChoice = (choiceId: string, endpoint: 'from' | 'to') => {
    updateActiveProject((project) => {
      const choice = project.choices.find((item) => item.id === choiceId)
      if (!choice) return project
      const fromScene = project.scenes.find((scene) => scene.id === choice.fromSceneId)
      const toScene = project.scenes.find((scene) => scene.id === choice.toSceneId)
      const anchorScene = endpoint === 'to' ? fromScene ?? toScene : toScene ?? fromScene
      const direction = endpoint === 'to' ? 1 : -1
      const position = anchorScene
        ? {
          x: anchorScene.position.x + direction * (NODE_WIDTH + 180),
          y: anchorScene.position.y + 40,
        }
        : defaultNewScenePosition()
      const scene = createDraftScene(`新场景 ${project.scenes.length + 1}`, position)
      return {
        ...project,
        scenes: [...project.scenes, scene],
        choices: project.choices.map((item) => (
          item.id === choiceId
            ? {
              ...item,
              fromSceneId: endpoint === 'from' ? scene.id : item.fromSceneId,
              toSceneId: endpoint === 'to' ? scene.id : item.toSceneId,
            }
            : item
        )),
        selectedObject: { type: 'choice', id: choiceId },
      }
    })
  }

  const addChoice = () => {
    const lastCanvasSceneId = lastCanvasSceneIdByProjectRef.current[activeProject.id]
    const fromScene = scenes.find((scene) => scene.id === lastCanvasSceneId) ?? selectedScene ?? scenes[0]
    if (!fromScene) {
      message.warning('请先添加或选择一个场景')
      return
    }
    const choiceId = uniqueId('choice')
    const siblingCount = choices.filter((choice) => (
      choice.fromSceneId === fromScene.id && !choice.toSceneId
    )).length
    updateActiveProject((project) => ({
      ...project,
      choices: [
        ...project.choices,
        {
          id: choiceId,
          fromSceneId: fromScene.id,
          toSceneId: '',
          label: siblingCount > 0 ? `新的选择 ${siblingCount + 1}` : '新的选择',
          trigger: 'after_scene',
        },
      ],
      selectedObject: { type: 'choice', id: choiceId },
    }))
  }

  const deleteChoice = (choiceId: string) => {
    updateActiveProject((project) => {
      const nextChoices = project.choices.filter((choice) => choice.id !== choiceId)
      const selectedObjectWasDeleted = project.selectedObject.type === 'choice' && project.selectedObject.id === choiceId
      return {
        ...project,
        choices: nextChoices,
        selectedObject: selectedObjectWasDeleted
          ? firstSelectableObject(project.scenes, nextChoices, project.assetNodes)
          : project.selectedObject,
      }
    })
  }

  const confirmDeleteChoice = (choiceId: string) => {
    const choice = choices.find((item) => item.id === choiceId)
    if (!choice) return
    modal.confirm({
      title: `删除选择「${choice.label}」？`,
      content: '删除后会移除这条选择连线。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk() {
        deleteChoice(choiceId)
        message.success('选择已删除')
      },
    })
  }

  const deleteScene = (sceneId: string) => {
    updateActiveProject((project) => {
      const deletedChoiceIds = new Set(
        project.choices
          .filter((choice) => choice.fromSceneId === sceneId || choice.toSceneId === sceneId)
          .map((choice) => choice.id),
      )
      const nextScenes = project.scenes.filter((scene) => scene.id !== sceneId)
      const nextChoices = project.choices.filter((choice) => !deletedChoiceIds.has(choice.id))
      const nextNodeLinks = project.nodeLinks.filter((link) => (
        !(link.from.type === 'scene' && link.from.id === sceneId)
        && !(link.to.type === 'scene' && link.to.id === sceneId)
      ))
      const removedNodeLinkIds = new Set(project.nodeLinks.filter((link) => !nextNodeLinks.includes(link)).map((link) => link.id))
      const selectedObjectWasDeleted = (
        (project.selectedObject.type === 'scene' && project.selectedObject.id === sceneId)
        || (project.selectedObject.type === 'choice' && deletedChoiceIds.has(project.selectedObject.id))
        || (project.selectedObject.type === 'nodeLink' && removedNodeLinkIds.has(project.selectedObject.id))
      )
      const nextSelectedObject = selectedObjectWasDeleted
        ? firstSelectableObject(nextScenes, nextChoices, project.assetNodes)
        : project.selectedObject
      if (lastCanvasSceneIdByProjectRef.current[project.id] === sceneId) {
        lastCanvasSceneIdByProjectRef.current[project.id] = nextSelectedObject.type === 'scene' ? nextSelectedObject.id : ''
      }
      return {
        ...project,
        scenes: nextScenes,
        choices: nextChoices,
        nodeLinks: nextNodeLinks,
        selectedObject: nextSelectedObject,
      }
    })
  }

  const confirmDeleteScene = (sceneId: string) => {
    const scene = scenes.find((item) => item.id === sceneId)
    if (!scene) return
    const connectedChoiceCount = choices.filter((choice) => (
      choice.fromSceneId === sceneId || choice.toSceneId === sceneId
    )).length
    modal.confirm({
      title: `删除场景「${scene.title}」？`,
      content: connectedChoiceCount > 0
        ? `会同时删除 ${connectedChoiceCount} 个关联选择。`
        : '删除后会从画布中移除这个场景节点。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk() {
        deleteScene(sceneId)
        message.success('场景已删除')
      },
    })
  }

  const addLine = (sceneId: string) => {
    updateScene(sceneId, (scene) => ({
      ...scene,
      script: {
        ...scene.script,
        lines: [
          ...scene.script.lines,
          {
            id: uniqueId('line'),
            speaker: '角色',
            text: '输入一句新的台词。',
          },
        ],
      },
    }))
  }

  const deleteLine = (sceneId: string, lineId: string) => {
    updateScene(sceneId, (scene) => ({
      ...scene,
      script: {
        ...scene.script,
        lines: scene.script.lines.filter((line) => line.id !== lineId),
      },
    }))
  }

  const startPreview = (sceneId = startScene?.id) => {
    if (!sceneId) return
    setPreviewSceneId(sceneId)
    setPreviewLineIndex(0)
    setPreviewChoicesVisible(false)
    setPreviewOpen(true)
  }

  const finishPreviewScene = () => {
    if (outgoingPreviewChoices.length > 0) {
      setPreviewChoicesVisible(true)
      return
    }
    message.info('预览已结束')
  }

  const advancePreview = () => {
    if (!previewScene) return
    if (previewLineIndex < previewScene.script.lines.length - 1) {
      setPreviewLineIndex((index) => index + 1)
      return
    }
    finishPreviewScene()
  }

  const choosePreviewEdge = (choice: ChoiceEdge) => {
    if (!sceneMap.has(choice.toSceneId)) return
    setPreviewSceneId(choice.toSceneId)
    setPreviewLineIndex(0)
    setPreviewChoicesVisible(false)
  }

  useEffect(() => {
    if (!previewOpen || !previewScene || previewChoicesVisible || previewHasVideo || currentPreviewLine) return
    if (outgoingPreviewChoices.length > 0) {
      setPreviewChoicesVisible(true)
    }
  }, [
    currentPreviewLine,
    outgoingPreviewChoices.length,
    previewChoicesVisible,
    previewHasVideo,
    previewOpen,
    previewScene,
  ])

  const refreshReleaseHistory = async (projectId = activeProject.id) => {
    if (!hasCloudCopy(activeProject)) {
      setReleaseHistory([])
      return
    }
    setReleaseLoading(true)
    try {
      const releases = await listInteractiveMovieReleases(projectId)
      setReleaseHistory(releases)
    } catch (error) {
      message.error(resolveErrorMessage(error))
    } finally {
      setReleaseLoading(false)
    }
  }

  const openPublishModal = () => {
    setPublishModalOpen(true)
    void refreshReleaseHistory(activeProject.id)
  }

  const publishCurrentDraft = async () => {
    if (!activeProject.version || !activeProject.contentHash) {
      message.warning('请先保存到云端后再发表')
      return
    }
    if (activeProjectHasUnsavedChanges) {
      message.warning('请先保存当前草稿后再发表')
      return
    }
    setPublishing(true)
    try {
      const result = await publishInteractiveMovieProject<InteractiveMovieProject>(
        activeProject.id,
        activeProject.version,
        activeProject.contentHash,
      )
      replaceProjectFromServer(result.project)
      await refreshReleaseHistory(activeProject.id)
      setSyncMessage(`已发表正式版 v${result.release.version_no}`)
      message.success(`已发表正式版 v${result.release.version_no}`)
    } catch (error) {
      message.error(resolveErrorMessage(error))
    } finally {
      setPublishing(false)
    }
  }

  const setReleaseOnline = async (release: InteractiveMovieRelease) => {
    setPublishing(true)
    try {
      const detail = await setInteractiveMoviePublishedRelease<InteractiveMovieProject>(activeProject.id, release.id)
      replaceProjectFromServer(detail)
      await refreshReleaseHistory(activeProject.id)
      setSyncMessage(`已切换线上版 v${release.version_no}`)
      message.success(`已切换线上版 v${release.version_no}`)
    } catch (error) {
      message.error(resolveErrorMessage(error))
    } finally {
      setPublishing(false)
    }
  }

  const closePublishedProject = async () => {
    if (!activeProject.isPublished) return
    modal.confirm({
      title: '关闭发表？',
      content: '关闭后固定公开 URL 会立即变为 404，正式版历史仍会保留。',
      okText: '关闭发表',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        setPublishing(true)
        try {
          const detail = await closeInteractiveMoviePublication<InteractiveMovieProject>(activeProject.id)
          replaceProjectFromServer(detail)
          await refreshReleaseHistory(activeProject.id)
          setSyncMessage('已关闭发表')
          message.success('已关闭发表')
        } catch (error) {
          message.error(resolveErrorMessage(error))
          throw error
        } finally {
          setPublishing(false)
        }
      },
    })
  }

  const saveDraft = useCallback(async () => {
    const draft = activeProject
    if (!draft || saving) return
    writeProjectReplica(draftReplicaKey(draft.id), draft)
    persistWorkspaceLocally(workspace)
    setSaving(true)
    try {
      const cloudBase = readProjectReplica(cloudReplicaKey(draft.id))
      if (!cloudBase?.version || !cloudBase.contentHash) {
        const created = await createInteractiveMovieProject(draft.title, draft)
        const project = withCloudMeta(created)
        writeProjectReplica(cloudReplicaKey(project.id), project)
        writeProjectReplica(draftReplicaKey(project.id), project)
        setWorkspace((current) => ({
          activeProjectId: project.id,
          projects: current.projects.map((item) => (item.id === draft.id ? project : item)),
        }))
        setSyncMessage('已保存到云端')
        message.success('已保存到云端')
        return
      }
      const patch = buildProjectPatch(cloudBase, draft)
      if (!patchHasChanges(patch)) {
        setSyncMessage('云端已是最新')
        message.success('云端已是最新')
        return
      }
      const saved = await patchInteractiveMovieProject<InteractiveMovieProject>(draft.id, patch)
      const project = withCloudMeta(saved)
      writeProjectReplica(cloudReplicaKey(project.id), project)
      writeProjectReplica(draftReplicaKey(project.id), project)
      setWorkspace((current) => ({
        ...current,
        projects: current.projects.map((item) => (item.id === project.id ? project : item)),
      }))
      setSyncMessage('已保存到云端')
      message.success('已保存到云端')
    } catch (error) {
      if (isMissingCloudProjectError(error)) {
        cleanupMissingCloudProject(draft.id)
        message.warning('云端项目不存在，已清理本地副本')
        return
      }
      const text = resolveErrorMessage(error)
      setSyncMessage(text)
      message.error(text)
    } finally {
      setSaving(false)
    }
  }, [activeProject, cleanupMissingCloudProject, message, saving, workspace])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        event.stopPropagation()
        if (event.repeat) return
        void saveDraft()
      }
      const target = event.target as HTMLElement | null
      const isEditingText = target?.closest('input, textarea, [contenteditable="true"]')
      if (!isEditingText && selectedObject.type === 'nodeLink' && (event.key === 'Delete' || event.key === 'Backspace')) {
        event.preventDefault()
        event.stopPropagation()
        deleteNodeLink(selectedObject.id)
      }
    }
    window.addEventListener('keydown', handleKeyDown, true)
    return () => window.removeEventListener('keydown', handleKeyDown, true)
  }, [deleteNodeLink, saveDraft, selectedObject])

  useEffect(() => {
    if (!cloudReady || !activeProject?.contentHash) return undefined
    const syncOnce = async () => {
      if (syncing || saving) return
      setSyncing(true)
      try {
        const remote = await getInteractiveMovieSyncState(activeProject.id)
        const cloudBase = readProjectReplica(cloudReplicaKey(activeProject.id))
        if (!cloudBase || remote.content_hash === cloudBase.contentHash) {
          setSyncMessage('云端已同步')
          return
        }
        const draft = readProjectReplica(draftReplicaKey(activeProject.id)) ?? activeProject
        const localPatch = buildProjectPatch(cloudBase, draft)
        if (patchHasChanges(localPatch)) {
          setSyncMessage('云端有新版本，本地有未保存修改')
          return
        }
        const latest = await getInteractiveMovieProject<InteractiveMovieProject>(activeProject.id)
        const project = withCloudMeta(latest)
        writeProjectReplica(cloudReplicaKey(project.id), project)
        writeProjectReplica(draftReplicaKey(project.id), project)
        setWorkspace((current) => ({
          ...current,
          projects: current.projects.map((item) => (item.id === project.id ? project : item)),
        }))
        setSyncMessage('已自动同步云端')
      } catch (error) {
        if (isMissingCloudProjectError(error)) {
          cleanupMissingCloudProject(activeProject.id)
          return
        }
        setSyncMessage('云端同步检查失败')
      } finally {
        setSyncing(false)
      }
    }
    const timer = window.setInterval(() => {
      void syncOnce()
    }, 60_000)
    return () => window.clearInterval(timer)
  }, [activeProject, cleanupMissingCloudProject, cloudReady, saving, syncing])

  const uploadAssetFile = async (asset: AssetNode, file: File) => {
    setUploadByAssetId((current) => ({
      ...current,
      [asset.id]: { status: 'uploading', message: asset.type === 'image' ? '图片上传中' : '视频上传中' },
    }))
    try {
      const uploaded = asset.type === 'image'
        ? await uploadInteractiveMovieImage(file)
        : await uploadInteractiveMovieVideo(file)
      if (!uploaded.url) {
        setUploadByAssetId((current) => ({
          ...current,
          [asset.id]: { status: 'failed', message: '上传成功，但没有返回可访问 URL' },
        }))
        message.warning('上传成功，但没有返回可访问 URL')
        return
      }
      updateAsset(asset.id, (current) => ({
        ...current,
        media: {
          url: uploaded.url ?? undefined,
          objectKey: uploaded.object_key,
          storageUri: uploaded.storage_uri,
          contentType: uploaded.content_type,
          size: uploaded.size,
          status: 'ready',
        },
      }))
      setUploadByAssetId((current) => ({
        ...current,
        [asset.id]: { status: 'ready', message: `已上传：${uploaded.filename}` },
      }))
      message.success(asset.type === 'image' ? '图片已上传' : '视频已上传')
    } catch (error) {
      const text = resolveErrorMessage(error)
      setUploadByAssetId((current) => ({
        ...current,
        [asset.id]: { status: 'failed', message: text },
      }))
      message.error(text)
    }
  }

  const uploadSceneAsset = async (scene: SceneNode, type: 'image' | 'video', file: File) => {
    try {
      const uploaded = type === 'image'
        ? await uploadInteractiveMovieImage(file)
        : await uploadInteractiveMovieVideo(file)
      if (!uploaded.url) {
        message.warning('上传成功，但没有返回可访问 URL')
        return
      }
      if (type === 'image') {
        updateScene(scene.id, (current) => ({
          ...current,
          media: {
            ...current.media,
            posterUrl: uploaded.url ?? undefined,
            coverImageNodeId: '',
            status: 'ready',
          },
        }))
        message.success('封面图片已上传')
        return
      }
      const asset = createDraftAssetNode(
        type,
        uploaded.filename,
        {
          x: scene.position.x + NODE_WIDTH + 80,
          y: scene.position.y,
        },
      )
      const uploadedAsset: AssetNode = {
        ...asset,
        media: {
          url: uploaded.url ?? undefined,
          objectKey: uploaded.object_key,
          storageUri: uploaded.storage_uri,
          contentType: uploaded.content_type,
          size: uploaded.size,
          status: 'ready',
        },
      }
      updateActiveProject((project) => ({
        ...project,
        assetNodes: [...project.assetNodes, uploadedAsset],
        scenes: project.scenes.map((item) => (
          item.id === scene.id
            ? {
              ...item,
              media: {
                ...item.media,
                kind: 'video',
                videoNodeId: uploadedAsset.id,
              },
            }
            : item
        )),
        selectedObject: { type: uploadedAsset.type, id: uploadedAsset.id },
      }))
      message.success('视频已上传并关联')
    } catch (error) {
      message.error(resolveErrorMessage(error))
    }
  }


  return {
    activeProject,
    activeProjectHasUnsavedChanges,
    activeProjectPublicUrl,
    addAssetNode,
    addChoice,
    addLine,
    addScene,
    advancePreview,
    assetMap,
    assetNodes,
    beginChoiceDrag,
    beginLinkDrag,
    beginNodeDrag,
    beginNodeLinkEndpointDrag,
    beginNodeLinkRouteDrag,
    beginPan,
    bottomToolbarCollapsed,
    canvasContextMenu,
    canvasRef,
    choices,
    closePublishedProject,
    confirmDeleteAssetNode,
    confirmDeleteChoice,
    confirmDeleteProject,
    confirmDeleteScene,
    confirmRenameProject,
    createProject,
    createSceneForChoice,
    currentPreviewLine,
    choosePreviewEdge,
    deleteLine,
    deleteNodeLink,
    endPointerInteraction,
    fitView,
    finishPreviewScene,
    handlePointerMove,
    handleWheel,
    imageNodes,
    linkDraft,
    nodeLinks,
    openCanvasContextMenu,
    openPublishModal,
    outgoingPreviewChoices,
    previewChoicesVisible,
    previewHasVideo,
    previewOpen,
    previewPosterUrl,
    previewScene,
    previewVideoUrl,
    promptTemplate,
    publishCurrentDraft,
    publishModalOpen,
    publishing,
    refreshReleaseHistory,
    releaseHistory,
    releaseLoading,
    renameProject,
    rightPanelCollapsed,
    runContextMenuAction,
    saveDraft,
    saving,
    sceneMap,
    scenePanelState,
    scenes,
    selectCanvasScene,
    selectedAsset,
    selectedChoice,
    selectedNodeLink,
    selectedObject,
    selectedScene,
    setBottomToolbarCollapsed,
    setPreviewOpen,
    setPublishModalOpen,
    setReleaseOnline,
    setRightPanelCollapsed,
    setScenePanelState,
    setSelectedObject,
    setWorkspaceCollapsed,
    startPreview,
    switchProject,
    syncing,
    syncMessage,
    updateAsset,
    updateChoice,
    updateScene,
    uploadAssetFile,
    uploadByAssetId,
    uploadSceneAsset,
    videoNodes,
    viewport,
    workspace,
    workspaceCollapsed,
    zoomBy,
  }
}

export type InteractiveMoviePageModel = ReturnType<typeof useInteractiveMoviePageModel>
