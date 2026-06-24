import { Alert, Button, Col, Flex, List, Row, Space, Switch, Tag, Typography, theme } from 'antd'
import { EyeOutlined, GlobalOutlined, InfoCircleOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { useGestureControl } from '../../hooks/useGestureControl'
import type { GestureControlState } from '../../contexts/GestureControlContext'

const gestureStateMeta: Record<GestureControlState, { color: string; label: string }> = {
  error: { color: 'error', label: '异常' },
  loading: { color: 'processing', label: '启动中' },
  off: { color: 'default', label: '未开启' },
  ready: { color: 'success', label: '待识别' },
  tracking: { color: 'success', label: '识别中' },
}

const gestureGuides = [
  '移动食指或手掌位置，屏幕上会出现全局手势光标。',
  '对准可点击元素后短暂捏合，可触发点击。',
  '握拳后移动，可拖拽或进入滑动状态。',
  '上下滑动会滚动当前页面。',
  '左右滑动会继续广播给支持手势事件的局部组件。',
]

export default function GestureControlPage() {
  const { token } = theme.useToken()
  const gesture = useGestureControl()
  const stateMeta = gestureStateMeta[gesture.state]

  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 16,
  }

  const subtleStyle = {
    background: token.colorFillAlter,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 14,
  }

  const handleToggle = () => {
    void gesture.toggle()
  }

  return (
    <Flex vertical gap={16}>
      <section style={sectionStyle}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={16}>
          <Flex vertical gap={6}>
            <Space align="center">
              <VideoCameraOutlined />
              <Typography.Title level={3} style={{ margin: 0 }}>
                手势操作
              </Typography.Title>
            </Space>
            <Typography.Text type="secondary">
              入口放在工具页；开启后识别能力仍在站内全局生效，可切到其他页面继续使用。
            </Typography.Text>
          </Flex>
          <Space align="center" size={12}>
            <Tag color={stateMeta.color}>{stateMeta.label}</Tag>
            <Switch
              aria-label="手势操作开关"
              checked={gesture.enabled}
              checkedChildren="开启"
              disabled={gesture.loading}
              loading={gesture.loading}
              onChange={handleToggle}
              unCheckedChildren="关闭"
            />
            {gesture.panelAvailable && !gesture.panelVisible && (
              <Button icon={<EyeOutlined />} onClick={gesture.showPanel}>
                显示全局侧栏
              </Button>
            )}
          </Space>
        </Flex>
      </section>

      <Alert
        showIcon
        type="info"
        message="全局控制，局部入口"
        description="打开开关后，浏览器会请求摄像头权限。识别只由当前浏览器会话驱动；手动关闭、切到后台或刷新页面都会释放摄像头。"
      />

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} lg={12}>
          <section style={{ ...sectionStyle, height: '100%' }}>
            <Flex vertical gap={12}>
              <Space align="center">
                <InfoCircleOutlined />
                <Typography.Title level={5} style={{ margin: 0 }}>
                  当前状态
                </Typography.Title>
              </Space>
              <Flex vertical gap={8} style={subtleStyle}>
                <Typography.Text type="secondary">识别反馈</Typography.Text>
                <Typography.Text strong>{gesture.statusMessage}</Typography.Text>
                <Typography.Text code style={{ wordBreak: 'break-word' }}>
                  {gesture.debugMessage}
                </Typography.Text>
              </Flex>
              {gesture.state === 'error' && (
                <Alert
                  showIcon
                  type="warning"
                  message="手势操作未启动"
                  description="请检查摄像头权限、浏览器支持情况，或确认摄像头没有被其他应用占用。"
                />
              )}
              {gesture.panelAvailable && (
                <Alert
                  showIcon
                  type={gesture.panelVisible ? 'success' : 'warning'}
                  message={gesture.panelVisible ? '全局侧栏已显示' : '全局侧栏已隐藏'}
                  description={gesture.panelVisible
                    ? '侧栏会保留在全局页面上，可以拖动到合适位置；关闭手势不会收起侧栏。'
                    : '侧栏被手动隐藏后才会隐藏；需要查看状态或重新开启手势时，可以在这里重新显示侧栏。'}
                  action={!gesture.panelVisible ? (
                    <Button size="small" icon={<EyeOutlined />} onClick={gesture.showPanel}>
                      显示
                    </Button>
                  ) : undefined}
                />
              )}
            </Flex>
          </section>
        </Col>
        <Col xs={24} lg={12}>
          <section style={{ ...sectionStyle, height: '100%' }}>
            <Flex vertical gap={12}>
              <Space align="center">
                <GlobalOutlined />
                <Typography.Title level={5} style={{ margin: 0 }}>
                  操作说明
                </Typography.Title>
              </Space>
              <List
                dataSource={gestureGuides}
                renderItem={(item) => (
                  <List.Item style={{ paddingInline: 0 }}>
                    <Typography.Text>{item}</Typography.Text>
                  </List.Item>
                )}
              />
            </Flex>
          </section>
        </Col>
      </Row>
    </Flex>
  )
}
