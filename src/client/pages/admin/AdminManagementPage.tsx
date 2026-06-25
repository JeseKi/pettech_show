import { ApiOutlined, AppstoreAddOutlined, BarChartOutlined, FileSearchOutlined, KeyOutlined, LockOutlined, TeamOutlined } from '@ant-design/icons'
import { Tabs } from 'antd'
import AdminMonitoringPage from './AdminMonitoringPage'
import UserManagementPage from './UserManagementPage'
import PermissionManagementPage from './PermissionManagementPage'
import ScopeManagementPage from './ScopeManagementPage'
import OAuthClientManagementPage from './OAuthClientManagementPage'
import AiwikiAuditPage from './AiwikiAuditPage'
import SkillMarketManagementPage from './SkillMarketManagementPage'
import AgentMarketManagementPage from './AgentMarketManagementPage'

const tabItems = [
  {
    key: 'monitoring',
    label: (
      <span>
        <BarChartOutlined />
        监控概览
      </span>
    ),
    children: <AdminMonitoringPage />,
  },
  {
    key: 'users',
    label: (
      <span>
        <TeamOutlined />
        用户管理
      </span>
    ),
    children: <UserManagementPage />,
  },
  {
    key: 'scopes',
    label: (
      <span>
        <LockOutlined />
        权限范围管理
      </span>
    ),
    children: <ScopeManagementPage />,
  },
  {
    key: 'permissions',
    label: (
      <span>
        <KeyOutlined />
        权限管理
      </span>
    ),
    children: <PermissionManagementPage />,
  },
  {
    key: 'oauth-clients',
    label: (
      <span>
        <ApiOutlined />
        OAuth Clients
      </span>
    ),
    children: <OAuthClientManagementPage />,
  },
  {
    key: 'agent-market',
    label: (
      <span>
        <AppstoreAddOutlined />
        智能体市场
      </span>
    ),
    children: <AgentMarketManagementPage />,
  },
  {
    key: 'skill-market',
    label: (
      <span>
        <AppstoreAddOutlined />
        技能市场
      </span>
    ),
    children: <SkillMarketManagementPage />,
  },
  {
    key: 'aiwiki-audit',
    label: (
      <span>
        <FileSearchOutlined />
        知识库审计
      </span>
    ),
    children: <AiwikiAuditPage />,
  },
]

export default function AdminManagementPage() {
  return (
    <div style={{ overflowX: 'auto' }}>
      <Tabs defaultActiveKey="monitoring" items={tabItems} style={{ minWidth: 500 }} />
    </div>
  )
}
