import { Button, Card, Col, Flex, Row, Typography } from 'antd'
import { BarChartOutlined, BookOutlined, FileSearchOutlined, FileTextOutlined, RightOutlined, TableOutlined } from '@ant-design/icons'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  AGENT_TOOL,
  CAPABILITY_GROUP_META,
  CONTENT_GROWTH_TOOL,
  GESTURE_CONTROL_TOOL,
  INTERACTIVE_MOVIE_TOOL,
  PERSONAL_AIWIKI_TOOL,
  WECHAT_AUTOMATION_FLOW_TOOL,
  WECOM_MOMENTS_PUBLISH_TOOL,
  VISIBLE_CAPABILITY_ENTRIES,
  type CapabilityGroupId,
} from '../../lib/workflowModes'

const capabilityGroupIcons: Record<CapabilityGroupId, ReactNode> = {
  'competitor-insights': <FileSearchOutlined />,
  'topic-planning': <TableOutlined />,
  'script-creation': <FileTextOutlined />,
}

const entryGroups = [
  {
    title: '内容增长',
    icon: <BarChartOutlined />,
    entries: [CONTENT_GROWTH_TOOL],
  },
  {
    title: '工具',
    icon: <BookOutlined />,
    entries: [AGENT_TOOL, PERSONAL_AIWIKI_TOOL, GESTURE_CONTROL_TOOL, WECHAT_AUTOMATION_FLOW_TOOL, WECOM_MOMENTS_PUBLISH_TOOL, INTERACTIVE_MOVIE_TOOL],
  },
  ...Object.entries(CAPABILITY_GROUP_META).map(([groupId, meta]) => ({
    title: meta.title,
    icon: capabilityGroupIcons[groupId as CapabilityGroupId],
    entries: VISIBLE_CAPABILITY_ENTRIES.filter((entry) => entry.group === groupId),
  })).filter((group) => group.entries.length > 0),
]

export default function DashboardPage() {
  return (
    <Flex vertical gap={24}>
      <Typography.Title level={2} style={{ margin: 0 }}>
        首页
      </Typography.Title>
      {entryGroups.map((group) => (
        <Flex key={group.title} vertical gap={12}>
          <Flex align="center" gap={8}>
            {group.icon}
            <Typography.Title level={4} style={{ margin: 0 }}>
              {group.title}
            </Typography.Title>
          </Flex>
          <Row gutter={[16, 16]}>
            {group.entries.map((entry) => (
              <Col key={entry.key} xs={24} md={12} xl={8}>
                <Card
                  hoverable
                  title={(
                    <Flex align="center" gap={8}>
                      {group.icon}
                      <span>{entry.navLabel}</span>
                    </Flex>
                  )}
                  extra={(
                    <Button type="link" icon={<RightOutlined />} iconPosition="end">
                      <Link to={entry.path}>进入</Link>
                    </Button>
                  )}
                  style={{ height: '100%' }}
                  styles={{ body: { minHeight: 152 } }}
                >
                  <Flex vertical justify="space-between" gap={16} style={{ height: '100%' }}>
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      {entry.description}
                    </Typography.Paragraph>
                    <Button type="primary" icon={group.icon} style={{ alignSelf: 'flex-start' }}>
                      <Link to={entry.path}>{entry.buttonText}</Link>
                    </Button>
                  </Flex>
                </Card>
              </Col>
            ))}
          </Row>
        </Flex>
      ))}
    </Flex>
  )
}
