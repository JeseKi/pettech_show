import { ApiOutlined, AppstoreAddOutlined, BarChartOutlined, FileSearchOutlined, KeyOutlined, LockOutlined, TeamOutlined } from '@ant-design/icons'
import { Tabs } from 'antd'
import AdminMonitoringPage from './AdminMonitoringPage'
import UserManagementPage from './UserManagementPage'
import PermissionManagementPage from './PermissionManagementPage'
import ScopeManagementPage from './ScopeManagementPage'
import OAuthClientManagementPage from './OAuthClientManagementPage'
import AiwikiAuditPage from './AiwikiAuditPage'
import SkillMarketManagementPage from './SkillMarketManagementPage'

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
        Scope 管理
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
    key: 'skill-market',
    label: (
      <span>
        <AppstoreAddOutlined />
        Skill 市场
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
