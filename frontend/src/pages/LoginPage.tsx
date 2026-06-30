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
  const { token } = theme.useToken()

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
                      rules={[{ required: true, message: '请输入用户名' }]}
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
                      ]}
                    >
                      <Input.Password
                        prefix={<LockOutlined />}
                        placeholder="密码"
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
        </div>
      </div>
    </div>
  )
}
