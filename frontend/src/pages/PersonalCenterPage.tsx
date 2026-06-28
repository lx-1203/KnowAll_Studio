import { useState, useEffect, useCallback } from 'react'
import {
  Tabs, Card, Form, Input, Button, Avatar, message, List, Tag, Badge,
  Empty, Popconfirm, Modal, Typography, Space, Spin, Select, Divider
} from 'antd'
import {
  UserOutlined, MailOutlined, PhoneOutlined, KeyOutlined,
  LinkOutlined, DisconnectOutlined, HistoryOutlined, BellOutlined,
  EditOutlined, SaveOutlined, CloseOutlined, ExclamationCircleOutlined
} from '@ant-design/icons'
import {
  getUserProfile, updateUserProfile, changePassword, getUserBinds,
  bindAccount, unbindAccount, getUserHistory, getNotifications,
  markNotificationRead, markAllNotificationsRead, deleteNotification,
  batchDeleteNotifications
} from '../api'
import type { UserProfile, UserBind, UserHistory as UserHistoryType, Notification as NotificationType } from '../types'

const { Text, Paragraph } = Typography

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  browse: { label: '浏览', color: 'blue' },
  quiz: { label: '测评', color: 'purple' },
  flashcard: { label: '闪卡', color: 'orange' },
  document: { label: '文档', color: 'green' },
  study: { label: '学习', color: 'cyan' },
  game: { label: '游戏', color: 'magenta' },
  order: { label: '订单', color: 'gold' },
  favorite: { label: '收藏', color: 'red' },
  search: { label: '搜索', color: 'geekblue' },
  chat: { label: '对话', color: 'lime' },
}

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  system: { label: '系统', color: 'blue' },
  quiz: { label: '测评', color: 'purple' },
  study: { label: '学习', color: 'cyan' },
  share: { label: '分享', color: 'green' },
  reminder: { label: '提醒', color: 'orange' },
}

export default function PersonalCenterPage() {
  const [activeTab, setActiveTab] = useState('profile')
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<UserProfile | null>(null)

  // Load profile on mount
  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    setLoading(true)
    try {
      const data = await getUserProfile()
      setProfile(data)
    } catch {
      message.error('加载用户信息失败')
    } finally {
      setLoading(false)
    }
  }

  const tabItems = [
    {
      key: 'profile',
      label: <span><UserOutlined />个人信息</span>,
      children: <ProfileTab profile={profile} onUpdate={loadProfile} />,
    },
    {
      key: 'security',
      label: <span><KeyOutlined />账号安全</span>,
      children: <SecurityTab />,
    },
    {
      key: 'history',
      label: <span><HistoryOutlined />操作记录</span>,
      children: <HistoryTab />,
    },
    {
      key: 'notifications',
      label: <span><BellOutlined />消息通知</span>,
      children: <NotificationTab />,
    },
  ]

  if (loading && !profile) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Avatar size={64} src={profile?.avatar_url || undefined} icon={!profile?.avatar_url ? <UserOutlined /> : undefined} />
          <div>
            <Text strong style={{ fontSize: 20 }}>{profile?.nickname || profile?.username || '用户'}</Text>
            <div style={{ color: '#888', fontSize: 13 }}>{profile?.email}</div>
          </div>
        </div>
      </Card>

      <Card styles={{ body: { padding: 0 } }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems}
          tabBarStyle={{ padding: '0 24px', marginBottom: 0 }} />
      </Card>
    </div>
  )
}

// ==================== Profile Tab ====================

function ProfileTab({ profile, onUpdate }: { profile: UserProfile | null; onUpdate: () => void }) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    if (profile) {
      form.setFieldsValue({
        nickname: profile.nickname,
        phone: profile.phone,
        email: profile.email,
        avatar_url: profile.avatar_url,
      })
    }
  }, [profile, form])

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      await updateUserProfile(values)
      message.success('个人信息已更新')
      setEditing(false)
      onUpdate()
    } catch (err: any) {
      if (err?.errorFields) return // form validation
      message.error(err?.response?.data?.detail || '更新失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        {!editing ? (
          <Button type="primary" icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑资料</Button>
        ) : (
          <Space>
            <Button icon={<CloseOutlined />} onClick={() => { setEditing(false); form.resetFields() }}>取消</Button>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存</Button>
          </Space>
        )}
      </div>

      <Form form={form} layout="vertical" disabled={!editing}>
        <Form.Item label="昵称" name="nickname" rules={[{ max: 100, message: '昵称不超过100字符' }]}>
          <Input placeholder="设置你的昵称" prefix={<UserOutlined />} />
        </Form.Item>
        <Form.Item label="手机号" name="phone" rules={[
          { pattern: /^[+]?[\d\s-]*$/, message: '手机号格式不正确' },
          { max: 20, message: '手机号不超过20字符' },
        ]}>
          <Input placeholder="绑定手机号" prefix={<PhoneOutlined />} />
        </Form.Item>
        <Form.Item label="邮箱" name="email" rules={[
          { type: 'email', message: '邮箱格式不正确' },
          { max: 255, message: '邮箱不超过255字符' },
        ]}>
          <Input placeholder="你的邮箱地址" prefix={<MailOutlined />} />
        </Form.Item>
        <Form.Item label="头像 URL" name="avatar_url" rules={[{ max: 500, message: '不超过500字符' }]}>
          <Input placeholder="输入头像图片链接" />
        </Form.Item>
      </Form>

      <Divider />
      <div style={{ color: '#888', fontSize: 12 }}>
        <div>用户名: {profile?.username}（不可修改）</div>
        <div>注册时间: {profile?.created_at ? new Date(profile.created_at).toLocaleString('zh-CN') : '-'}</div>
      </div>
    </div>
  )
}

// ==================== Security Tab ====================

const PROVIDER_ICONS: Record<string, string> = {
  wechat: '#07C160', qq: '#12B7F5', github: '#333', google: '#4285F4',
}

function SecurityTab() {
  const [pwdModalOpen, setPwdModalOpen] = useState(false)
  const [pwdSaving, setPwdSaving] = useState(false)
  const [binds, setBinds] = useState<UserBind[]>([])
  const [bindLoading, setBindLoading] = useState(false)
  const [pwdForm] = Form.useForm()

  useEffect(() => { loadBinds() }, [])

  const loadBinds = async () => {
    setBindLoading(true)
    try {
      const data = await getUserBinds()
      setBinds(data)
    } catch {
      message.error('加载绑定信息失败')
    } finally {
      setBindLoading(false)
    }
  }

  const handleChangePwd = async () => {
    try {
      const values = await pwdForm.validateFields()
      setPwdSaving(true)
      await changePassword({ old_password: values.old_password, new_password: values.new_password })
      message.success('密码修改成功')
      setPwdModalOpen(false)
      pwdForm.resetFields()
    } catch (err: any) {
      if (err?.errorFields) return
      message.error(err?.response?.data?.detail || '修改失败')
    } finally {
      setPwdSaving(false)
    }
  }

  const handleBind = async (provider: string) => {
    try {
      await bindAccount({ provider, provider_name: '', provider_uid: '' })
      message.success(`成功绑定 ${provider} 账号`)
      loadBinds()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '绑定失败')
    }
  }

  const handleUnbind = async (provider: string) => {
    try {
      await unbindAccount(provider)
      message.success(`已解除 ${provider} 绑定`)
      loadBinds()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '解绑失败')
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Card size="small" title="修改密码" style={{ marginBottom: 24 }}>
        <Button icon={<KeyOutlined />} onClick={() => setPwdModalOpen(true)}>修改密码</Button>
      </Card>

      <Card size="small" title="第三方账号绑定">
        <Spin spinning={bindLoading}>
          {binds.length === 0 ? (
            <Empty description="暂无绑定信息" />
          ) : (
            <List
              dataSource={binds}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    item.is_bound ? (
                      <Popconfirm
                        key="unbind"
                        title={`确定解除 ${item.provider_name} 的绑定？`}
                        onConfirm={() => handleUnbind(item.provider)}
                        okText="确定" cancelText="取消"
                      >
                        <Button size="small" danger icon={<DisconnectOutlined />}>解绑</Button>
                      </Popconfirm>
                    ) : (
                      <Button key="bind" size="small" type="primary" icon={<LinkOutlined />}
                        onClick={() => handleBind(item.provider)}>绑定</Button>
                    ),
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      <div style={{
                        width: 32, height: 32, borderRadius: 6,
                        background: PROVIDER_ICONS[item.provider] || '#999',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: '#fff', fontWeight: 700, fontSize: 16,
                      }}>
                        {item.provider_name.charAt(0).toUpperCase()}
                      </div>
                    }
                    title={item.provider_name}
                    description={
                      item.is_bound
                        ? <Tag color="green">已绑定{item.bound_at ? ` · ${new Date(item.bound_at).toLocaleDateString('zh-CN')}` : ''}</Tag>
                        : <Tag>未绑定</Tag>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Spin>
      </Card>

      <Modal
        title="修改密码"
        open={pwdModalOpen}
        onOk={handleChangePwd}
        onCancel={() => { setPwdModalOpen(false); pwdForm.resetFields() }}
        confirmLoading={pwdSaving}
        okText="确认修改"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={pwdForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="old_password" label="原密码"
            rules={[{ required: true, message: '请输入原密码' }]}>
            <Input.Password placeholder="输入当前密码" />
          </Form.Item>
          <Form.Item name="new_password" label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码不能少于6个字符' },
              { max: 128, message: '密码不能超过128个字符' },
            ]}>
            <Input.Password placeholder="输入新密码" />
          </Form.Item>
          <Form.Item name="confirm" label="确认新密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) return Promise.resolve()
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}>
            <Input.Password placeholder="再次输入新密码" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// ==================== History Tab ====================

function HistoryTab() {
  const [data, setData] = useState<UserHistoryType[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filterType, setFilterType] = useState('')

  const fetchHistory = useCallback(async (pageNum: number, type: string) => {
    setLoading(true)
    try {
      const res = await getUserHistory(pageNum, pageSize, type)
      setData(res.items)
      setTotal(res.total)
    } catch {
      message.error('加载操作记录失败')
    } finally {
      setLoading(false)
    }
  }, [pageSize])

  useEffect(() => {
    fetchHistory(page, filterType)
  }, [page, filterType, fetchHistory])

  const handleFilterChange = (value: string) => {
    setFilterType(value)
    setPage(1)
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16 }}>
        <Select
          placeholder="按操作类型筛选"
          allowClear
          style={{ width: 160 }}
          value={filterType || undefined}
          onChange={(val) => handleFilterChange(val || '')}
          options={Object.entries(ACTION_LABELS).map(([key, { label }]) => ({ value: key, label }))}
        />
      </div>
      <List
        loading={loading}
        dataSource={data}
        locale={{ emptyText: <Empty description="暂无操作记录" /> }}
        renderItem={(item) => {
          const action = ACTION_LABELS[item.action_type] || { label: item.action_type, color: 'default' }
          return (
            <List.Item>
              <List.Item.Meta
                avatar={<Tag color={action.color}>{action.label}</Tag>}
                title={item.action_label || `${action.label}了${item.resource_type}`}
                description={item.detail && item.detail !== '{}' ? (
                  <Paragraph ellipsis={{ rows: 1 }} style={{ color: '#999', margin: 0 }}>
                    {item.detail}
                  </Paragraph>
                ) : undefined}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                {new Date(item.created_at).toLocaleString('zh-CN')}
              </Text>
            </List.Item>
          )
        }}
        pagination={{
          current: page,
          pageSize,
          total,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
          showSizeChanger: false,
        }}
      />
    </div>
  )
}

// ==================== Notification Tab ====================

function NotificationTab() {
  const [data, setData] = useState<NotificationType[]>([])
  const [total, setTotal] = useState(0)
  const [unreadCount, setUnreadCount] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('') // '' | '0' | '1'
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const fetchNotifications = useCallback(async (pageNum: number, readFilter: string) => {
    setLoading(true)
    try {
      const res = await getNotifications(pageNum, pageSize, readFilter)
      setData(res.items)
      setTotal(res.total)
      setUnreadCount(res.unread_count)
    } catch {
      message.error('加载通知失败')
    } finally {
      setLoading(false)
    }
  }, [pageSize])

  useEffect(() => {
    fetchNotifications(page, filter)
  }, [page, filter, fetchNotifications])

  const handleMarkRead = async (id: string) => {
    try {
      await markNotificationRead(id)
      message.success('已标记为已读')
      fetchNotifications(page, filter)
    } catch {
      message.error('操作失败')
    }
  }

  const handleMarkAllRead = async () => {
    Modal.confirm({
      title: '确认操作',
      icon: <ExclamationCircleOutlined />,
      content: '确定将所有未读通知标记为已读？',
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        try {
          await markAllNotificationsRead()
          message.success('全部已标记为已读')
          fetchNotifications(page, filter)
        } catch {
          message.error('操作失败')
        }
      },
    })
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteNotification(id)
      message.success('已删除')
      fetchNotifications(page, filter)
    } catch {
      message.error('删除失败')
    }
  }

  const handleBatchDelete = () => {
    if (selectedIds.length === 0) {
      message.warning('请先选择通知')
      return
    }
    Modal.confirm({
      title: '确认删除',
      icon: <ExclamationCircleOutlined />,
      content: `确定删除选中的 ${selectedIds.length} 条通知？`,
      okText: '确定删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await batchDeleteNotifications(selectedIds)
          message.success(`已删除 ${selectedIds.length} 条通知`)
          setSelectedIds([])
          fetchNotifications(page, filter)
        } catch {
          message.error('操作失败')
        }
      },
    })
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  const toggleSelectAll = () => {
    if (selectedIds.length === data.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(data.map((n) => n.id))
    }
  }

  const tabItems = [
    { key: '', label: `全部 (${total})` },
    { key: '0', label: `未读 (${unreadCount})` },
    { key: '1', label: `已读 (${total - unreadCount})` },
  ]

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <Space>
          {tabItems.map((t) => (
            <Button
              key={t.key}
              type={filter === t.key ? 'primary' : 'default'}
              size="small"
              onClick={() => { setFilter(t.key); setPage(1); setSelectedIds([]) }}
            >
              {t.label}
            </Button>
          ))}
        </Space>
        <Space>
          <Button size="small" onClick={toggleSelectAll}>
            {selectedIds.length === data.length && data.length > 0 ? '取消全选' : '全选'}
          </Button>
          <Button size="small" danger disabled={selectedIds.length === 0} onClick={handleBatchDelete}>
            批量删除
          </Button>
          <Button size="small" type="link" onClick={handleMarkAllRead} disabled={unreadCount === 0}>
            全部已读
          </Button>
        </Space>
      </div>
      <List
        loading={loading}
        dataSource={data}
        locale={{ emptyText: <Empty description="暂无通知" /> }}
        renderItem={(item) => {
          const cat = CATEGORY_LABELS[item.category] || { label: item.category, color: 'default' }
          return (
            <List.Item
              style={{
                background: item.is_read ? undefined : '#f0f5ff',
                padding: '12px 16px',
                borderRadius: 6,
                marginBottom: 4,
                cursor: 'pointer',
              }}
              onClick={() => toggleSelect(item.id)}
              actions={[
                !item.is_read && (
                  <Button key="read" type="link" size="small"
                    onClick={(e) => { e.stopPropagation(); handleMarkRead(item.id) }}>
                    标为已读
                  </Button>
                ),
                <Button key="delete" type="link" size="small" danger
                  onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}>
                  删除
                </Button>,
              ].filter(Boolean)}
            >
              <List.Item.Meta
                avatar={
                  <Space>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.id)}
                      onClick={(e) => e.stopPropagation()}
                      onChange={() => toggleSelect(item.id)}
                    />
                    <Tag color={cat.color} style={{ margin: 0 }}>{cat.label}</Tag>
                  </Space>
                }
                title={
                  <span style={{ fontWeight: item.is_read ? 'normal' : 600 }}>
                    {!item.is_read && <Badge status="processing" style={{ marginRight: 6 }} />}
                    {item.title}
                  </span>
                }
                description={
                  <div>
                    <Paragraph ellipsis={{ rows: 2 }} style={{ color: '#666', margin: '4px 0' }}>
                      {item.content}
                    </Paragraph>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {new Date(item.created_at).toLocaleString('zh-CN')}
                    </Text>
                  </div>
                }
              />
            </List.Item>
          )
        }}
        pagination={{
          current: page,
          pageSize,
          total,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
          showSizeChanger: false,
        }}
      />
    </div>
  )
}
