import type { AssetNode, AssetNodeType, ChoiceEdge, InteractiveMovieProject, SceneNode, SelectedObject, VideoPromptParts } from './interactiveMovieTypes'
import { uniqueId } from './interactiveMovieConstants'

export const defaultPromptParts = (sceneTitle: string): VideoPromptParts => ({
  subject: sceneTitle,
  action: '',
  scene: '',
  camera: '电影级中景缓慢推近，浅景深',
  timeline: '[0-2s] 建立场景和主体状态；[2-5s] 主体完成关键动作并留下悬念。',
  style: '电影感，写实，低饱和，高对比，细腻光影',
  constraints: '不出现文字水印，不切换主角，主体外观保持一致',
})

export const buildVideoPrompt = (scene: SceneNode): string => {
  const parts = scene.script.promptParts ?? defaultPromptParts(scene.title)
  const sections = [
    ['主体', parts.subject],
    ['动作', parts.action || scene.script.synopsis],
    ['场景', parts.scene || scene.script.visualDescription],
    ['镜头', parts.camera],
    ['时序', parts.timeline],
    ['风格', parts.style],
    ['约束', parts.constraints],
  ]
  return sections
    .filter(([, value]) => value.trim())
    .map(([label, value]) => `${label}：${value.trim()}`)
    .join('\n')
}

export const createDefaultProject = (title = '互动电影草稿'): InteractiveMovieProject => {
  const startSceneId = uniqueId('scene-start')
  const nextSceneId = uniqueId('scene-next')
  const projectId = uniqueId('movie')
  return {
    id: projectId,
    title,
    updatedAt: new Date().toISOString(),
    selectedObject: { type: 'scene', id: startSceneId },
    viewport: { x: 360, y: 160, zoom: 1 },
    assetNodes: [],
    nodeLinks: [],
    scenes: [
      {
        id: startSceneId,
        title: '雨夜来信',
        role: 'start',
        position: { x: 0, y: 0 },
        media: { kind: 'placeholder', status: 'mock' },
        script: {
          synopsis: '雨夜，主角在旧公寓门口收到一封没有署名的信。',
          visualDescription: '狭窄的老式公寓走廊，窗外下着雨，暖黄色楼道灯闪烁，地上有一封湿掉的信。',
          videoPrompt: 'cinematic rainy night apartment hallway, warm flickering light, mysterious envelope on the floor, slow push-in, suspense mood',
          promptParts: {
            subject: '年轻女性林夏站在老式公寓走廊，手里拿着一封湿掉的信',
            action: '她迟疑地拆开信封，抬头看向走廊尽头',
            scene: '雨夜，狭窄老公寓走廊，暖黄色灯光闪烁，地面潮湿',
            camera: '电影级中景缓慢推近，浅景深，轻微手持感',
            timeline: '[0-2s] 她发现门口的信；[2-5s] 她蹲下捡起信并拆开，神情紧张',
            style: '悬疑短片，写实，低饱和，高对比，环境声紧张',
            constraints: '不出现文字水印，不切换主角，不夸张恐怖',
          },
          lines: [
            { id: uniqueId('line'), speaker: '林夏', text: '这封信……为什么会在我家门口？' },
          ],
        },
      },
      {
        id: nextSceneId,
        title: '门后的声音',
        role: 'middle',
        position: { x: 480, y: 90 },
        media: { kind: 'placeholder', status: 'mock' },
        script: {
          synopsis: '主角拆开信后，隔壁空置已久的房间传来轻轻的敲门声。',
          visualDescription: '镜头贴近主角手中的信纸，字迹慢慢显现；远处传来敲门声，走廊尽头的门缝透出蓝光。',
          videoPrompt: 'close-up of wet paper letter, ink appearing slowly, empty hallway door with blue light leak, subtle horror, cinematic shallow depth of field',
          promptParts: {
            subject: '林夏站在走廊中央，手中拿着展开的信纸',
            action: '她被身后的敲门声惊到，缓慢转身',
            scene: '老公寓走廊尽头的空房间门缝透出蓝光，空气潮湿',
            camera: '从信纸特写切到主角背影，随后缓慢拉远',
            timeline: '[0-2s] 信纸字迹显现；[2-5s] 远处响起敲门声，主角缓慢转身',
            style: '悬疑电影，冷暖光对比，克制恐怖，真实质感',
            constraints: '不出现额外角色，不出现字幕水印，主角服装和上一场保持一致',
          },
          lines: [
            { id: uniqueId('line'), speaker: '林夏', text: '可身后的门，已经响了。' },
          ],
        },
      },
    ],
    choices: [
      {
        id: uniqueId('choice'),
        fromSceneId: startSceneId,
        toSceneId: nextSceneId,
        label: '打开那封信',
        trigger: 'after_scene',
      },
    ],
  }
}

export const createDraftScene = (title: string, position: { x: number; y: number }): SceneNode => ({
  id: uniqueId('scene'),
  title,
  role: 'middle',
  position,
  media: { kind: 'placeholder', status: 'mock' },
  script: {
    synopsis: '补充这个场景要发生的关键事件。',
    visualDescription: '描述画面、人物位置、镜头运动和情绪氛围。',
    videoPrompt: 'describe the cinematic shot, action, mood and camera movement',
    promptParts: defaultPromptParts(title),
    lines: [{ id: uniqueId('line'), speaker: '角色', text: '新的剧情片段从这里开始。' }],
  },
})

export const createDraftAssetNode = (
  type: AssetNodeType,
  title: string,
  position: { x: number; y: number },
): AssetNode => ({
  id: uniqueId(type),
  type,
  title,
  position,
  text: type === 'text' ? '## 新文本\n\n输入 Markdown 内容。' : '',
  media: { status: 'empty' },
})

export const normalizeProjectShape = (project: InteractiveMovieProject): InteractiveMovieProject => ({
  ...project,
  assetNodes: Array.isArray(project.assetNodes) ? project.assetNodes : [],
  nodeLinks: Array.isArray(project.nodeLinks)
    ? project.nodeLinks.map((link) => ({ ...link, offsetX: link.offsetX ?? 0, offsetY: link.offsetY ?? 0 }))
    : [],
  choices: Array.isArray(project.choices)
    ? project.choices.map((choice) => ({ ...choice, offsetX: choice.offsetX ?? 0, offsetY: choice.offsetY ?? 0 }))
    : [],
  scenes: project.scenes.map((scene) => ({
    ...scene,
    media: {
      ...scene.media,
      videoNodeId: scene.media.videoNodeId ?? '',
      coverImageNodeId: scene.media.coverImageNodeId ?? '',
    },
  })),
})


export const normalizeProjectChoices = (project: InteractiveMovieProject): InteractiveMovieProject => {
  const choices = project.choices
    .map((choice) => {
      if (choice.fromSceneId !== choice.toSceneId) return choice
      const fallbackTarget = project.scenes.find((scene) => scene.id !== choice.fromSceneId)
      return fallbackTarget ? { ...choice, toSceneId: fallbackTarget.id } : null
    })
    .filter((choice): choice is ChoiceEdge => choice !== null)
  return { ...project, choices }
}


export const firstSelectableObject = (scenes: SceneNode[], choices: ChoiceEdge[], assetNodes: AssetNode[] = []): SelectedObject => {
  if (scenes[0]) return { type: 'scene', id: scenes[0].id }
  if (choices[0]) return { type: 'choice', id: choices[0].id }
  if (assetNodes[0]) return { type: assetNodes[0].type, id: assetNodes[0].id }
  return { type: 'scene', id: '' }
}
