import { useState, useEffect } from 'react'
import { Tabs, Form, Input, Button, Typography, App, theme, Divider, Space, message as antMsg } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined, QqOutlined, WechatOutlined, GithubOutlined, GoogleOutlined } from '@ant-design/icons'
import { login, register } from '../api'
import { useAuthStore } from '../stores'

const { Title, Text } = Typography

// OAuth providers configuration
const SOCIAL_LOGINS = [
  { provider: 'qq', icon: <QqOutlined />, label: 'QQ登录', color: '#12B7F5' },
  { provider: 'wechat', icon: <WechatOutlined />, label: '微信登录', color: '#07C160' },
  { provider: 'github', icon: <GithubOutlined />, label: 'GitHub', color: '#24292e' },
]

export default function LoginPage() {
  const { message } = App.useApp()
  const authLogin = useAuthStore(s => s.login)
  const [loading, setLoading] = useState(false)
  const [providers, setProviders] = useState<string[]>([])
  const { token } = theme.useToken()

  // Check available OAuth providers
  useEffect(() => {
    fetch('/api/v1/oauth/providers')
      .then(r => r.json())
      .then(data => setProviders((data.providers || []).map((p: any) => p.provider)))
      .catch(() => {})
  }, [])

  // Handle OAuth callback (token in URL fragment after redirect)
  useEffect(() => {
    const hash = window.location.hash
    if (hash.includes('oauth_token=')) {
      const params = new URLSearchParams(hash.slice(1))
      const token = params.get('oauth_token')
      const userId = params.get('user_id')
      const username = params.get('username')
      if (token) {
        authLogin(token, { id: userId || '', username: username || '', email: '' })
        message.success(`${params.get('provider') || '第三方'}登录成功`)
        window.location.hash = ''
      }
    }
  }, [])

  const handleSocialLogin = (provider: string) => {
    window.location.href = `/api/v1/oauth/${provider}/login?redirect_to=/`
  }

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const data = await login(values)
      authLogin(data.access_token, data.user)
      message.success('登录成功')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (values: { username: string; email: string; password: string }) => {
    setLoading(true)
    try {
      const data = await register(values)
      authLogin(data.access_token, data.user)
      message.success('注册成功，已自动登录')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '注册失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="page-fade"
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: token.colorBgLayout,
        transition: 'background 0.3s ease',
      }}
    >
      <div style={{ width: 420, padding: '0 16px' }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <img
            src="/logo.png"
            alt="全息坚果 Logo"
            style={{ width: 96, height: 96, borderRadius: 16, objectFit: 'cover', marginBottom: 12 }}
          />
          <Title
            level={2}
            style={{
              marginBottom: 4,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: token.colorTextHeading,
            }}
          >
            KnowAll Studio
          </Title>
          <Text style={{ fontSize: 15, color: token.colorTextSecondary }}>
            大学生学习系统
          </Text>
        </div>

        {/* Card */}
        <div
          style={{
            background: token.colorBgContainer,
            borderRadius: 12,
            padding: '28px 24px 12px',
            boxShadow: token.boxShadowTertiary,
            transition: 'background 0.3s ease, box-shadow 0.3s ease',
          }}
        >
          <Tabs
            centered
            items={[
              {
                key: 'login',
                label: '登录',
                children: (
                  <Form onFinish={handleLogin} size="large">
                    <Form.Item
                      name="username"
                      rules={[{ required: true, message: '请输入用户名或邮箱' }]}
                    >
                      <Input
                        prefix={<UserOutlined />}
                        placeholder="用户名 / 邮箱"
                        autoComplete="username"
                      />
                    </Form.Item>
                    <Form.Item
                      name="password"
                      rules={[{ required: true, message: '请输入密码' }]}
                    >
                      <Input.Password
                        prefix={<LockOutlined />}
                        placeholder="密码"
                        autoComplete="current-password"
                      />
                    </Form.Item>
                    <Form.Item style={{ marginBottom: 12 }}>
                      <Button type="primary" htmlType="submit" loading={loading} block>
                        登录
                      </Button>
                    </Form.Item>
                  </Form>
                ),
              },
              {
                key: 'register',
                label: '注册',
                children: (
                  <Form onFinish={handleRegister} size="large">
                    <Form.Item
                      name="username"
                      rules={[
                        { required: true, message: '请输入用户名' },
                        { pattern: /^[a-zA-Z0-9_\u4e00-\u9fff]{2,50}$/, message: '2-50字符，中英文、数字、下划线' },
                      ]}
                    >
                      <Input
                        prefix={<UserOutlined />}
                        placeholder="用户名"
                        maxLength={50}
                      />
                    </Form.Item>
                    <Form.Item
                      name="email"
                      rules={[
                        { required: true, message: '请输入邮箱' },
                        { type: 'email', message: '邮箱格式不正确' },
                      ]}
                    >
                      <Input
                        prefix={<MailOutlined />}
                        placeholder="邮箱"
                        autoComplete="email"
                      />
                    </Form.Item>
                    <Form.Item
                      name="password"
                      rules={[
                        { required: true, message: '请输入密码' },
                        { min: 6, message: '密码至少 6 位' },
                        { max: 128, message: '密码不能超过 128 位' },
                      ]}
                    >
                      <Input.Password
                        prefix={<LockOutlined />}
                        placeholder="密码（至少6位）"
                        autoComplete="new-password"
                      />
                    </Form.Item>
                    <Form.Item
                      name="confirm_password"
                      dependencies={['password']}
                      rules={[
                        { required: true, message: '请确认密码' },
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
                        prefix={<LockOutlined />}
                        placeholder="确认密码"
                        autoComplete="new-password"
                      />
                    </Form.Item>
                    <Form.Item style={{ marginBottom: 12 }}>
                      <Button type="primary" htmlType="submit" loading={loading} block>
                        注册
                      </Button>
                    </Form.Item>
                  </Form>
                ),
              },
            ]}
          />

          {/* Social Login */}
          {providers.length > 0 && (
            <>
              <Divider plain style={{ fontSize: 13, color: '#999' }}>
                第三方登录
              </Divider>
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <Space size={12}>
                  {SOCIAL_LOGINS.filter(s => providers.includes(s.provider)).map(s => (
                    <Button
                      key={s.provider}
                      shape="circle"
                      size="large"
                      icon={s.icon}
                      onClick={() => handleSocialLogin(s.provider)}
                      style={{
                        color: s.color,
                        borderColor: s.color,
                        fontSize: 22,
                      }}
                      title={s.label}
                    />
                  ))}
                </Space>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
