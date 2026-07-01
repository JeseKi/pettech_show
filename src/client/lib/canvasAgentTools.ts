export const FRONTEND_CANVAS_PREFIX = 'frontend_canvas__'

export const FRONTEND_CANVAS_UNAVAILABLE_MESSAGE = '请在画布中和智能体进行对话, 当前环境无法直接操作画布.'

export const canvasToolDefinitions: Array<Record<string, unknown>> = [
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}get_overview`,
      description: '获取当前互动电影画布概括，只包含节点关系、节点 title 和节点类型。',
      parameters: { type: 'object', properties: {}, additionalProperties: false },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}get_node_detail`,
      description: '按 type 和 id 获取一个画布对象的完整详情。type 可为 scene、text、image、video、asset、choice、nodeLink。',
      parameters: {
        type: 'object',
        properties: { type: { type: 'string' }, id: { type: 'string' } },
        required: ['type', 'id'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}create_node`,
      description: '创建场景或素材节点。type 可为 scene、text、image、video。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['scene', 'text', 'image', 'video'] },
          title: { type: 'string' },
          position: {
            type: 'object',
            properties: { x: { type: 'number' }, y: { type: 'number' } },
            required: ['x', 'y'],
            additionalProperties: false,
          },
          role: { type: 'string', enum: ['start', 'middle', 'ending'] },
          script: { type: 'object' },
          text: { type: 'string' },
          media: { type: 'object' },
        },
        required: ['type'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}update_node`,
      description: '更新场景或素材节点。type 可为 scene、text、image、video，patch 放需要修改的字段。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['scene', 'text', 'image', 'video'] },
          id: { type: 'string' },
          patch: { type: 'object' },
        },
        required: ['type', 'id', 'patch'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}delete_node`,
      description: '删除场景或素材节点。删除时会清理相关选择线、节点连接和场景媒体引用。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['scene', 'text', 'image', 'video'] },
          id: { type: 'string' },
        },
        required: ['type', 'id'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}create_relation`,
      description: '创建画布关系。type=choice 创建场景选择线；type=nodeLink 创建普通节点连接线。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['choice', 'nodeLink'] },
          fromSceneId: { type: 'string' },
          toSceneId: { type: 'string' },
          label: { type: 'string' },
          from: { type: 'object' },
          to: { type: 'object' },
        },
        required: ['type'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}update_relation`,
      description: '更新选择线或普通节点连接线。type 可为 choice 或 nodeLink。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['choice', 'nodeLink'] },
          id: { type: 'string' },
          patch: { type: 'object' },
        },
        required: ['type', 'id', 'patch'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}delete_relation`,
      description: '删除选择线或普通节点连接线。type 可为 choice 或 nodeLink。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['choice', 'nodeLink'] },
          id: { type: 'string' },
        },
        required: ['type', 'id'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}apply_operations`,
      description: '批量执行多个画布操作，适合一次性创建知识库图、批量创建节点和连线，减少多轮工具调用。每个 operation.action 可为 create_node、update_node、delete_node、create_relation、update_relation、delete_relation。',
      parameters: {
        type: 'object',
        properties: {
          operations: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                action: {
                  type: 'string',
                  enum: ['create_node', 'update_node', 'delete_node', 'create_relation', 'update_relation', 'delete_relation'],
                },
                type: { type: 'string' },
                id: { type: 'string' },
                title: { type: 'string' },
                position: { type: 'object' },
                patch: { type: 'object' },
                role: { type: 'string' },
                script: { type: 'object' },
                text: { type: 'string' },
                media: { type: 'object' },
                fromSceneId: { type: 'string' },
                toSceneId: { type: 'string' },
                label: { type: 'string' },
                from: { type: 'object' },
                to: { type: 'object' },
              },
              required: ['action'],
              additionalProperties: true,
            },
          },
        },
        required: ['operations'],
        additionalProperties: false,
      },
    },
  },
]
