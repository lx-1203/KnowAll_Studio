import { useState, useEffect } from 'react'
import { Card, Button, Input, Select, Space, App, Table, Tag, Statistic, Row, Col } from 'antd'
import { KeyOutlined, ApiOutlined, DatabaseOutlined, BarChartOutlined } from '@ant-design/icons'
import { addAPIKey, getQuotaStatus, getCacheStats } from '../api'

export default function SettingsPage() {
  const [provider, setProvider] = useState('deepseek')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [quota, setQuota] = useState<any>({})
  const [cacheStats, setCacheStats] = useState<any>({})
  const { message } = App.useApp()

  useEffect(() => {
    getQuotaStatus().then(setQuota).catch(console.error)
    getCacheStats().then(setCacheStats).catch(console.error)
  }, [])

  const handleAddKey = async () => {
    if (!apiKey.trim()) { message.warning('请输入 API Key'); return }
    setSaving(true)
    try {
      await addAPIKey({ provider, api_key: apiKey, key_alias: `${provider}-key` })
      message.success('API Key 已添加')
      setApiKey('')
    } catch (e: any) {
      message.error('添加失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Card><Statistic title="今日用量" value={quota.used_today || 0} suffix="tokens" /></Card></Col>
        <Col span={8}><Card><Statistic title="剩余额度" value={quota.remaining || 0} suffix="tokens" /></Card></Col>
        <Col span={8}><Card><Statistic title="缓存条目" value={cacheStats.total_entries || 0} suffix="条" /></Card></Col>
      </Row>

      <Card title={<Space><ApiOutlined /> 多模型 API 配置</Space>} style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            <Select value={provider} onChange={setProvider} style={{ width: 160 }}
              options={[
                { value: 'deepseek', label: 'DeepSeek' },
                { value: 'openai', label: 'OpenAI' },
                { value: 'qwen', label: '通义千问' },
                { value: 'zhipu', label: '智谱AI' },
                { value: 'ollama', label: 'Ollama (本地)' },
              ]} />
            <Input.Password value={apiKey} onChange={e => setApiKey(e.target.value)}
              placeholder="输入 API Key..." style={{ width: 400 }} />
            <Button icon={<KeyOutlined />} type="primary" loading={saving} onClick={handleAddKey}>
              添加密钥
            </Button>
          </Space>
          <span style={{ color: '#999', fontSize: 12 }}>
            密钥仅加密存储在本地，不会上传至任何第三方。仅文本片段通过密钥调用外部模型 API。
          </span>
        </Space>
      </Card>

      <Card title={<Space><DatabaseOutlined /> 本地存储说明</Space>} style={{ marginBottom: 16 }}>
        <ul style={{ lineHeight: 2 }}>
          <li>所有原始文档 100% 保存在本地 <Tag>documents/</Tag> 目录</li>
          <li>知识树、题库、闪卡、学习记录存储在本机 SQLite 数据库</li>
          <li>向量检索库存储在 <Tag>vector_db/</Tag> (ChromaDB)</li>
          <li>仅精简文本片段调用外部大模型 API 用于内容生成</li>
          <li>断网后：复习、刷题、导图查看不受影响，仅 AI 生成功能暂停</li>
        </ul>
      </Card>

      <Card title={<Space><BarChartOutlined /> API 调用成本估算</Space>}>
        <Table
          dataSource={[
            { model: 'DeepSeek V3', input: '$0.14/M', output: '$0.28/M', suitable: '日常出题/制卡 (推荐)' },
            { model: 'GPT-4o', input: '$5.00/M', output: '$15.00/M', suitable: '复杂任务/高精度' },
            { model: 'GPT-4o-mini', input: '$0.15/M', output: '$0.60/M', suitable: '批量生成/低成本' },
            { model: 'Qwen Turbo', input: '$0.40/M', output: '$1.20/M', suitable: '中文内容优化' },
            { model: 'Ollama 本地', input: '免费', output: '免费', suitable: '100%离线/无成本' },
          ]}
          rowKey="model"
          columns={[
            { title: '模型', dataIndex: 'model', key: 'model' },
            { title: '输入价格', dataIndex: 'input', key: 'input' },
            { title: '输出价格', dataIndex: 'output', key: 'output' },
            { title: '适用场景', dataIndex: 'suitable', key: 'suitable' },
          ]}
        />
      </Card>
    </div>
  )
}
