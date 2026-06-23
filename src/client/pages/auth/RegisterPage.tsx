import {
  Alert,
  App,
  Button,
  Card,
  Flex,
  Form,
  Input,
  Space,
  Spin,
  Typography,
} from 'antd'
import {
  LockOutlined,
  UserAddOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import TurnstileWidget from '../../components/auth/TurnstileWidget'
import { useAuth } from '../../hooks/useAuth'
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig'
import { resolveApiErrorMessage } from '../../lib/error'
import BrandLogo from '../../components/brand/BrandLogo'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { register, loading, isAuthenticated } = useAuth()
  const { turnstile } = useRuntimeConfig()
  const { message } = App.useApp()
  const turnstileSiteKey = turnstile.siteKey
  const turnstileEnabled = turnstile.enabled

  const [form] = Form.useForm<{ username: string; password: string; confirmPassword: string }>()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [registerTurnstileToken, setRegisterTurnstileToken] = useState<string | null>(null)

  useEffect(() => {
    if (!loading && isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, loading, navigate])

  const handleSubmit = async (values: { username: string; password: string; confirmPassword: string }) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { confirmPassword: _confirmPassword, ...payload } = values
    if (turnstileEnabled && !registerTurnstileToken) {
      const noTokenError = '请先完成机器人校验'
      setError(noTokenError)
      message.error(noTokenError)
      return
    }
    setSubmitting(true)
    setError(null)
    setSuccessMessage(null)
    try {
      await register({ ...payload, turnstile_token: registerTurnstileToken ?? undefined })
      setSuccessMessage('注册成功，请使用新账号登录。')
      message.success('注册成功')
      navigate('/login', { state: { registerSuccess: true } })
      form.resetFields()
    } catch (err) {
      const text = resolveApiErrorMessage(err, '注册失败，请稍后再试。')
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ minHeight: '100vh' }}
      >
        <Spin tip="正在加载，请稍候" size="large" />
      </Flex>
    )
  }

  return (
    <Flex
      align="center"
      justify="center"
      style={{ minHeight: '100vh', padding: '48px 16px' }}
    >
      <Card
        bordered={false}
        className="theme-card-shadow"
        style={{ width: '100%', maxWidth: 420 }}
      >
        <Space direction="vertical" size={24} style={{ width: '100%' }}>
          <div>
            <div style={{ marginBottom: 20 }}>
              <BrandLogo showTagline size={42} />
            </div>
            <Typography.Title level={3} style={{ marginBottom: 8 }}>
              创建新账号
            </Typography.Title>
            <Typography.Text type="secondary">
              使用用户名和密码创建账号。
            </Typography.Text>
          </div>
          {error && <Alert type="error" showIcon message={error} />}
          {successMessage && <Alert type="success" showIcon message={successMessage} />}
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
            requiredMark={false}
            autoComplete="on"
          >
            <Form.Item
              label="用户名"
              name="username"
              rules={[
                { required: true, message: '请输入用户名' },
                { min: 3, message: '用户名至少 3 个字符' },
              ]}
            >
              <Input
                size="large"
                prefix={<UserOutlined />}
                placeholder="请输入用户名"
                autoComplete="username"
                allowClear
              />
            </Form.Item>
            <Form.Item
              label="密码"
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 8, message: '密码至少 8 个字符' },
              ]}
            >
              <Input.Password
                size="large"
                prefix={<LockOutlined />}
                placeholder="请输入密码"
                autoComplete="new-password"
              />
            </Form.Item>
            <Form.Item
              label="确认密码"
              name="confirmPassword"
              dependencies={['password']}
              rules={[
                { required: true, message: '请再次输入密码' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('password') === value) {
                      return Promise.resolve()
                    }
                    return Promise.reject(new Error('两次输入的密码不一致'))
                  },
                }),
              ]}
            >
              <Input.Password
                size="large"
                prefix={<LockOutlined />}
                placeholder="请再次输入密码"
                autoComplete="new-password"
              />
            </Form.Item>
            {turnstileEnabled ? (
              <Form.Item>
                <TurnstileWidget
                  siteKey={turnstileSiteKey}
                  scriptUrl={turnstile.scriptUrl}
                  action="auth_register_with_code"
                  onToken={setRegisterTurnstileToken}
                />
              </Form.Item>
            ) : null}
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                size="large"
                icon={<UserAddOutlined />}
                loading={submitting}
                block
              >
                注册
              </Button>
            </Form.Item>
          </Form>
          <Flex justify="center" gap={8}>
            <Typography.Text type="secondary">已有账号？</Typography.Text>
            <Link to="/login" className="theme-link">
              返回登录
            </Link>
          </Flex>
        </Space>
      </Card>
    </Flex>
  )
}
