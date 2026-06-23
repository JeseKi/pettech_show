import { useNavigate } from 'react-router-dom'
import { Button, Tag, Avatar, Dropdown, Flex, Typography } from 'antd'
import { RocketOutlined, SafetyOutlined, ThunderboltOutlined, ToolOutlined, GlobalOutlined, MobileOutlined, UserOutlined, LogoutOutlined } from '@ant-design/icons'
import { useAuth } from '../../hooks/useAuth'
import BrandLogo from '../../components/brand/BrandLogo'
import { BRAND_NAME, BRAND_TAGLINE } from '../../lib/brand'

const features = [
  {
    icon: <ThunderboltOutlined className="text-3xl text-blue-500" />,
    title: '内容资产协同',
    desc: '沉淀素材、选题与知识资产，支撑团队高效创作',
  },
  {
    icon: <SafetyOutlined className="text-3xl text-green-500" />,
    title: '安全账号体系',
    desc: '支持双因素认证、设备管理与管理员权限控制',
  },
  {
    icon: <ToolOutlined className="text-3xl text-purple-500" />,
    title: '业务模块化',
    desc: '围绕内容生产、选题矩阵与长文生成持续扩展',
  },
  {
    icon: <GlobalOutlined className="text-3xl text-cyan-500" />,
    title: '精致界面体验',
    desc: '支持亮色与暗色主题，适配日常办公场景',
  },
  {
    icon: <MobileOutlined className="text-3xl text-orange-500" />,
    title: '多端可用',
    desc: '桌面与移动屏幕都能稳定访问核心工作流',
  },
  {
    icon: <RocketOutlined className="text-3xl text-red-500" />,
    title: '快速交付',
    desc: '前后端一体化工程，便于持续迭代和部署',
  },
]

const techStack = [
  'React 19', 'TypeScript', 'Vite', 'Tailwind CSS 4',
  'Ant Design 5', 'FastAPI', 'SQLAlchemy', 'Pydantic',
  'JWT Auth', 'TOTP 2FA', 'Alembic', 'Loguru',
]

export default function LandingPage() {
  const navigate = useNavigate()
  const { isAuthenticated, user, logout } = useAuth()

  const handleLogout = async () => {
    await logout()
    navigate('/', { replace: true })
  }

  const userMenuItems = [
    {
      key: 'user',
      icon: <UserOutlined />,
      label: (
        <Flex vertical gap={2} style={{ minWidth: 160 }}>
          <Typography.Text type="secondary">当前用户</Typography.Text>
          <Typography.Text strong>{user?.username ?? '未登录'}</Typography.Text>
        </Flex>
      ),
      disabled: true,
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  return (
    <div className="min-h-screen bg-[var(--app-bg)] text-[var(--app-text-primary)] transition-colors duration-300">
      {/* Header */}
      <header className="fixed top-0 w-full z-50 bg-[var(--app-elevated-bg)] backdrop-blur-md border-b border-[var(--app-border-color)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="text-xl font-bold tracking-tight">
            <BrandLogo showTagline size={36} />
          </div>
          {isAuthenticated ? (
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" arrow>
              <Avatar
                icon={<UserOutlined />}
                style={{ background: '#1668dc', cursor: 'pointer' }}
              />
            </Dropdown>
          ) : (
            <Button
              type="primary"
              size="small"
              onClick={() => navigate('/login')}
            >
              登录
            </Button>
          )}
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <Tag color="gold" className="mb-4">{BRAND_TAGLINE}</Tag>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6">
            {BRAND_NAME}
          </h1>
          <p className="text-lg sm:text-xl text-[var(--app-text-secondary)] max-w-2xl mx-auto mb-8 leading-relaxed">
            面向内容创意、选题策划与广告投放协作的工作台，
            将素材沉淀、知识整理和长文生成集中在一个清晰可靠的界面中。
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            {isAuthenticated ? (
              <Button
                type="primary"
                size="large"
                className="h-12 px-8 text-base font-medium"
                onClick={() => navigate('/dashboard')}
              >
                进入工作台
              </Button>
            ) : (
              <>
                <Button
                  type="primary"
                  size="large"
                  className="h-12 px-8 text-base font-medium"
                  onClick={() => navigate('/register')}
                >
                  免费开始使用
                </Button>
                <Button
                  size="large"
                  className="h-12 px-8 text-base font-medium"
                  onClick={() => navigate('/login')}
                >
                  已有账号？登录
                </Button>
              </>
            )}
          </div>
          {!isAuthenticated && (
            <p className="mt-4 text-sm text-[var(--app-text-secondary)]">
              安全登录 · 权限管理 · 即刻协作
            </p>
          )}
        </div>
      </section>

      {/* Tech Stack */}
      <section className="py-12 px-4 sm:px-6 lg:px-8 border-y border-[var(--app-border-color)]">
        <div className="max-w-7xl mx-auto">
          <p className="text-center text-sm text-[var(--app-text-secondary)] mb-6 uppercase tracking-wider">
            技术栈
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {techStack.map((tech) => (
              <Tag key={tech} className="text-sm py-1 px-3">
                {tech}
              </Tag>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              为什么选择{BRAND_NAME}？
            </h2>
            <p className="text-lg text-[var(--app-text-secondary)] max-w-2xl mx-auto">
              让内容资产、创意规划和执行管理保持在同一条工作链路上
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="p-6 rounded-2xl bg-[var(--app-elevated-bg)] border border-[var(--app-border-color)] theme-card-shadow hover:translate-y-[-4px] transition-all duration-300"
              >
                <div className="mb-4">{feature.icon}</div>
                <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                <p className="text-[var(--app-text-secondary)] leading-relaxed">
                  {feature.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <div className="p-10 sm:p-16 rounded-3xl bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-cyan-500/10 border border-[var(--app-border-color)]">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              {isAuthenticated ? '继续处理今天的工作？' : '准备好开始协作了吗？'}
            </h2>
            <p className="text-lg text-[var(--app-text-secondary)] mb-8 max-w-xl mx-auto">
              {isAuthenticated
                ? '回到工作台，继续推进内容与投放任务'
                : '创建账号，进入中影广告的内容协作工作台'}
            </p>
            <Button
              type="primary"
              size="large"
              className="h-12 px-8 text-base font-medium"
              onClick={() => navigate(isAuthenticated ? '/dashboard' : '/register')}
            >
              {isAuthenticated ? '进入工作台' : '立即注册'}
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 sm:px-6 lg:px-8 border-t border-[var(--app-border-color)]">
        <div className="max-w-7xl mx-auto text-center text-sm text-[var(--app-text-secondary)]">
          <p>© 2026 {BRAND_NAME}. 开源项目，MIT 许可证。</p>
        </div>
      </footer>
    </div>
  )
}
