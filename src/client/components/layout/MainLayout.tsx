import { useMemo, useState, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import {
  Avatar,
  Dropdown,
  Flex,
  Layout,
  Menu,
  Modal,
  type MenuProps,
  Typography,
  theme,
  Button,
  Drawer,
} from 'antd'
const { Header, Content, Sider } = Layout
import {
  LogoutOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  DashboardOutlined,
  SettingOutlined,
  SafetyOutlined,
  TabletOutlined,
  BarChartOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  TableOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig'
import ProfilePage from '../../pages/profile/ProfilePage'
import SecurityPage from '../../pages/profile/SecurityPage'
import DevicesPage from '../../pages/profile/DevicesPage'
import BrandLogo from '../brand/BrandLogo'
import {
  CAPABILITY_GROUP_META,
  CONTENT_GROWTH_TOOL,
  TOOL_ENTRIES,
  VISIBLE_CAPABILITY_ENTRIES,
  type CapabilityGroupId,
} from '../../lib/workflowModes'

const workflowEntries = [
  ...TOOL_ENTRIES,
  CONTENT_GROWTH_TOOL,
  ...VISIBLE_CAPABILITY_ENTRIES,
]

const capabilityGroupIcons: Record<CapabilityGroupId, ReactNode> = {
  'competitor-insights': <FileSearchOutlined />,
  'topic-planning': <TableOutlined />,
  'script-creation': <FileTextOutlined />,
}

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()
  const { user, logout, logoutAllDevices } = useAuth()
  const { infoDistribution } = useRuntimeConfig()
  const [collapsed, setCollapsed] = useState(true)
  const [isMobile, setIsMobile] = useState(false)
  const [settingsModalOpen, setSettingsModalOpen] = useState(false)
  const [settingsActiveKey, setSettingsActiveKey] = useState('profile')
  const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false)
  const [siderWidth, setSiderWidth] = useState(64)
  const siderRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  useEffect(() => {
    if (isMobile) {
      setCollapsed(true)
    }
  }, [isMobile])

  useEffect(() => {
    const siderElement = siderRef.current
    if (!siderElement) return

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width
        setSiderWidth(width)
      }
    })

    resizeObserver.observe(siderElement)

    return () => {
      resizeObserver.disconnect()
    }
  }, [])

  const selectedKeys = useMemo(() => {
    if (location.pathname.startsWith('/profile')) {
      if (location.pathname.includes('/security')) {
        return ['security']
      }
      if (location.pathname.includes('/devices')) {
        return ['devices']
      }
      return ['profile']
    }
    if (location.pathname.startsWith('/admin')) {
      return ['admin']
    }
    if (location.pathname.startsWith(CONTENT_GROWTH_TOOL.path)) {
      return [CONTENT_GROWTH_TOOL.key]
    }
    const workflowEntry = workflowEntries.find((entry) => location.pathname === entry.path)
    if (workflowEntry) {
      return [workflowEntry.key]
    }
    if (location.pathname.startsWith('/')) {
      return ['dashboard']
    }
    return []
  }, [location.pathname])

  const menuItems = useMemo<MenuProps['items']>(() => {
    const items: MenuProps['items'] = [
      {
        key: 'dashboard',
        icon: <DashboardOutlined />,
        label: <Link to="/dashboard">首页</Link>,
      },
      {
        key: CONTENT_GROWTH_TOOL.key,
        icon: <BarChartOutlined />,
        label: <Link to={CONTENT_GROWTH_TOOL.path}>{CONTENT_GROWTH_TOOL.navLabel}</Link>,
      },
      {
        key: 'tools-group',
        icon: <VideoCameraOutlined />,
        label: '工具',
        children: TOOL_ENTRIES.map((entry) => {
          if ('externalConfigKey' in entry) {
            const href = infoDistribution.baseUrl
            return {
              key: entry.key,
              disabled: !href,
              label: href
                ? <a href={href} target="_blank" rel="noreferrer">{entry.navLabel}</a>
                : <span title="请先配置 INFO_DISTRIBUTION_BASE_URL">{entry.navLabel}</span>,
            }
          }

          return {
            key: entry.key,
            label: <Link to={entry.path}>{entry.navLabel}</Link>,
          }
        }),
      },
      ...Object.entries(CAPABILITY_GROUP_META).map(([groupId, meta]) => ({
        key: `${groupId}-group`,
        icon: capabilityGroupIcons[groupId as CapabilityGroupId],
        label: meta.title,
        children: VISIBLE_CAPABILITY_ENTRIES
          .filter((entry) => entry.group === groupId)
          .map((entry) => ({
            key: entry.key,
            label: <Link to={entry.path}>{entry.navLabel}</Link>,
          })),
      })).filter((item) => item.children.length > 0),
    ]

    if (user?.role === 'admin') {
      items.push({
        key: 'admin-group',
        icon: <SettingOutlined />,
        label: '管理员',
        children: [
          {
            key: 'admin',
            label: <Link to="/admin">管理员面板</Link>,
          },
        ],
      })
    }

    return items
  }, [infoDistribution.baseUrl, user?.role])

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const handleLogoutAllDevices = async () => {
    const confirmed = window.confirm('这会让所有已登录设备立即失效，是否继续？')
    if (!confirmed) {
      return
    }
    await logoutAllDevices()
    navigate('/login', { replace: true })
  }

  const userMenu = useMemo<MenuProps['items']>(
    () => [
      {
        key: 'current-user',
        icon: <UserOutlined />,
        label: (
          <Flex vertical gap={2} style={{ minWidth: 180 }}>
            <Typography.Text type="secondary">当前用户</Typography.Text>
            <Typography.Text strong>{user?.username ?? '未登录'}</Typography.Text>
          </Flex>
        ),
        disabled: true,
      },
      { type: 'divider' },
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
      },
    ],
    [user?.username],
  )

  const settingsMenu = useMemo<MenuProps['items']>(() => [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人信息',
    },
    {
      key: 'security',
      icon: <SafetyOutlined />,
      label: '安全',
    },
    {
      key: 'devices',
      icon: <TabletOutlined />,
      label: '设备管理',
    },
  ], [])

  const handleUserMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'logout') {
      void handleLogout()
      return
    }
    if (key === 'logout-all') {
      void handleLogoutAllDevices()
    }
  }

  const handleSettingsMenuClick: MenuProps['onClick'] = ({ key }) => {
    setSettingsActiveKey(key)
  }

  const handleMouseEnter = () => {
    if (!isMobile) {
      setCollapsed(false)
    }
  }

  const handleMouseLeave = () => {
    if (!isMobile) {
      setCollapsed(true)
    }
  }

  const toggleCollapsed = () => {
    setCollapsed(!collapsed)
  }

  const selectedWorkflowEntry = workflowEntries.find((entry) => entry.key === selectedKeys[0])

  const pageTitle = selectedWorkflowEntry?.navLabel ?? (selectedKeys[0] === 'admin'
    ? '管理员面板'
    : selectedKeys[0] === 'dashboard'
      ? '首页'
        : '')

  return (
    <Layout style={{ minHeight: '100vh', background: 'var(--app-bg)' }}>
      <Sider
        ref={siderRef}
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        collapsedWidth={isMobile ? 0 : 64}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
          overflowX: 'hidden',
          overflowY: 'auto',
          background: 'rgba(5, 7, 6, 0.9)',
          borderRight: '1px solid var(--app-border-subtle)',
          boxShadow: 'var(--app-header-shadow)',
          backdropFilter: 'blur(18px)',
        }}
        className={isMobile && collapsed ? 'hidden' : ''}
      >
        <Flex
          vertical
          justify="space-between"
          style={{ height: '100%' }}
        >
          <div>
            <Flex
              align="center"
              justify={collapsed ? 'center' : 'space-between'}
              style={{
                height: 56,
                paddingInline: collapsed ? 0 : 16,
                borderBottom: '1px solid var(--app-border-subtle)',
              }}
            >
              {collapsed ? (
                <Link to="/" aria-label="返回首页">
                  <BrandLogo compact size={30} />
                </Link>
              ) : (
                <>
                  <Link
                    to="/"
                    aria-label="返回首页"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      minWidth: 0,
                      color: token.colorTextHeading,
                    }}
                  >
                    <BrandLogo size={34} />
                  </Link>
                  <Button
                    type="text"
                    icon={<MenuFoldOutlined />}
                    onClick={toggleCollapsed}
                    style={{ marginLeft: 'auto' }}
                  />
                </>
              )}
            </Flex>
            <Menu
                mode="inline"
                theme="dark"
                selectedKeys={selectedKeys}
                items={menuItems}
                style={{
                  background: 'transparent',
                borderRight: 'none',
                padding: '8px 0',
              }}
            />
          </div>
          <Flex
            align="center"
            justify={collapsed ? 'center' : 'space-between'}
            style={{
              paddingInline: collapsed ? 0 : 16,
              paddingBlock: 12,
              borderTop: '1px solid var(--app-border-subtle)',
            }}
          >
            {collapsed ? (
              <Flex vertical gap={8} align="center">
                <Dropdown
                  menu={{ items: userMenu, onClick: handleUserMenuClick }}
                  placement="topRight"
                  arrow
                  trigger={['hover']}
                  getPopupContainer={() => document.body}
                  overlayStyle={{ zIndex: 1000 }}
                >
                  <Avatar
                    size="small"
                    icon={<UserOutlined />}
                    style={{ background: token.colorPrimary, cursor: 'pointer' }}
                  />
                </Dropdown>
              </Flex>
            ) : (
              <Flex align="center" gap={8} style={{ width: '100%' }}>
                <Dropdown
                  menu={{ items: userMenu, onClick: handleUserMenuClick }}
                  placement="topRight"
                  arrow
                  trigger={['hover']}
                  getPopupContainer={() => document.body}
                  overlayStyle={{ zIndex: 1000 }}
                >
                  <Flex align="center" gap={8} style={{ cursor: 'pointer', flex: 1 }}>
                    <Avatar
                      size="small"
                      icon={<UserOutlined />}
                      style={{ background: token.colorPrimary }}
                    />
                    <Typography.Text ellipsis style={{ flex: 1 }}>
                      {user?.username}
                    </Typography.Text>
                  </Flex>
                </Dropdown>
                {siderWidth > 176 && (
                  <Button
                    type="text"
                    size="small"
                    icon={<SettingOutlined />}
                    onClick={() => setSettingsModalOpen(true)}
                  />
                )}
              </Flex>
            )}
          </Flex>
        </Flex>
      </Sider>
      <Modal
        title={isMobile ? null : '设置'}
        open={settingsModalOpen}
        onCancel={() => {
          setSettingsModalOpen(false)
          setSettingsDrawerOpen(false)
        }}
        footer={null}
        width={isMobile ? '100%' : 1000}
        styles={{
          body: { padding: 0, height: '65vh' },
          ...(isMobile ? { header: { padding: '12px 16px', borderBottom: `1px solid ${token.colorBorder}` }, content: { margin: 0, top: 0, maxWidth: '100vw', borderRadius: 0 } } : {}),
        }}
      >
        <Layout style={{ height: '100%' }}>
          {isMobile ? (
            <>
              {!settingsDrawerOpen && (
                <Flex align="center" gap={8} style={{ padding: '0 16px', borderBottom: `1px solid ${token.colorBorder}` }}>
                  <Button
                    type="text"
                    icon={<MenuUnfoldOutlined />}
                    onClick={() => setSettingsDrawerOpen(true)}
                  />
                  <Typography.Text strong>
                    {settingsActiveKey === 'profile' ? '个人信息' : settingsActiveKey === 'security' ? '安全' : '设备管理'}
                  </Typography.Text>
                </Flex>
              )}
              <Drawer
                open={settingsDrawerOpen}
                onClose={() => setSettingsDrawerOpen(false)}
                placement="left"
                width={200}
                styles={{ body: { padding: 0 } }}
                title="设置"
              >
                <Menu
                  mode="inline"
                  selectedKeys={[settingsActiveKey]}
                  items={settingsMenu}
                  onClick={(e) => {
                    handleSettingsMenuClick(e)
                    setSettingsDrawerOpen(false)
                  }}
                  style={{ border: 'none', background: 'transparent' }}
                />
              </Drawer>
              <Content style={{ padding: '16px', background: token.colorBgContainer, overflow: 'auto' }}>
                {settingsActiveKey === 'profile' && <ProfilePage />}
                {settingsActiveKey === 'security' && <SecurityPage />}
                {settingsActiveKey === 'devices' && <DevicesPage />}
              </Content>
            </>
          ) : (
            <>
              <Sider width={200} style={{ background: token.colorBgContainer, borderRight: `1px solid ${token.colorBorder}` }}>
                <Menu
                  mode="inline"
                  selectedKeys={[settingsActiveKey]}
                  items={settingsMenu}
                  onClick={handleSettingsMenuClick}
                  style={{ border: 'none', background: 'transparent' }}
                />
              </Sider>
              <Content style={{ padding: '32px 40px', background: token.colorBgContainer, overflow: 'auto' }}>
                {settingsActiveKey === 'profile' && <ProfilePage />}
                {settingsActiveKey === 'security' && <SecurityPage />}
                {settingsActiveKey === 'devices' && <DevicesPage />}
              </Content>
            </>
          )}
        </Layout>
      </Modal>
      <Layout
        style={{
          marginLeft: isMobile
            ? 0
            : collapsed
              ? 64
              : 220,
          transition: 'margin-left 0.2s',
        }}
      >
        <Header
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 99,
            display: 'flex',
            alignItems: 'center',
            paddingInline: 16,
            paddingBlock: 12,
            background: 'rgba(5, 7, 6, 0.78)',
            borderBottom: '1px solid var(--app-border-subtle)',
            backdropFilter: 'blur(18px)',
          }}
        >
          {isMobile && (
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={toggleCollapsed}
            />
          )}
          <Typography.Title
            level={5}
            style={{ margin: 0, flex: 1, marginLeft: isMobile ? 8 : 0 }}
          >
            {pageTitle}
          </Typography.Title>
        </Header>
        <Content style={{ padding: '24px 16px 48px' }}>
          <div
            style={{
              margin: '0 auto',
              maxWidth: location.pathname.startsWith('/aiwiki')
                || location.pathname.startsWith('/content-growth')
                || location.pathname.startsWith('/wechat-automation-flow')
                || location.pathname.startsWith('/wecom-moments-publish')
                || location.pathname.startsWith('/competitor-insights')
                || location.pathname.startsWith('/topic-planning')
                || location.pathname.startsWith('/script-creation')
                ? 1600
                : 1120,
              width: '100%',
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
      {isMobile && !collapsed && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 99,
            background: 'rgba(0, 0, 0, 0.58)',
          }}
          onClick={toggleCollapsed}
        />
      )}
    </Layout>
  )
}
