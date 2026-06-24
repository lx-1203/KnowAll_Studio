import { Suspense, lazy } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Layout, Menu, Button, Spin } from 'antd'
import { FileTextOutlined, ApartmentOutlined, FormOutlined, IdcardOutlined, RobotOutlined, SettingOutlined, BulbOutlined, ThunderboltOutlined, DashboardOutlined, PlayCircleOutlined, ScheduleOutlined, ShareAltOutlined } from '@ant-design/icons'
import { useTheme } from './components/ThemeProvider'
import ErrorBoundary from './components/ErrorBoundary'

// Lazy-load all pages for code splitting
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const UploadPage = lazy(() => import('./pages/UploadPage'))
const KnowledgePage = lazy(() => import('./pages/KnowledgePage'))
const QuizPage = lazy(() => import('./pages/QuizPage'))
const FlashcardPage = lazy(() => import('./pages/FlashcardPage'))
const GamePage = lazy(() => import('./pages/GamePage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const PipelinePage = lazy(() => import('./pages/PipelinePage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const StudyPage = lazy(() => import('./pages/StudyPage'))
const SharePage = lazy(() => import('./pages/SharePage'))

const { Header, Sider, Content } = Layout

function PageLoader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
      <Spin size="large" tip="加载中..."><div style={{ minHeight: 200 }} /></Spin>
    </div>
  )
}

export default function App() {
  const location = useLocation()
  const { isDark, toggle } = useTheme()
  const selectedKey = '/' + location.pathname.split('/')[1] || '/'

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: <Link to="/">仪表盘</Link> },
    { key: '/upload', icon: <FileTextOutlined />, label: <Link to="/upload">资料导入</Link> },
    { key: '/knowledge', icon: <ApartmentOutlined />, label: <Link to="/knowledge">知识树</Link> },
    { key: '/quiz', icon: <FormOutlined />, label: <Link to="/quiz">题库测评</Link> },
    { key: '/flashcards', icon: <IdcardOutlined />, label: <Link to="/flashcards">记忆闪卡</Link> },
    { key: '/game', icon: <PlayCircleOutlined />, label: <Link to="/game">互动游戏</Link> },
    { key: '/chat', icon: <RobotOutlined />, label: <Link to="/chat">AI 对话</Link> },
    { key: '/pipeline', icon: <ThunderboltOutlined />, label: <Link to="/pipeline">全链路</Link> },
    { key: '/study', icon: <ScheduleOutlined />, label: <Link to="/study">学习计划</Link> },
    { key: '/share', icon: <ShareAltOutlined />, label: <Link to="/share">分享协作</Link> },
    { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">设置</Link> },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px', background: '#4f46e5' }}>
        <h1 style={{ color: '#fff', margin: 0, fontSize: 20, fontWeight: 700 }}>
          KnowAll Studio
        </h1>
        <Button type="text" icon={<BulbOutlined />} onClick={toggle}
          style={{ color: '#fff', fontSize: 18 }}
          title={isDark ? '浅色模式' : '深色模式'} />
      </Header>
      <Layout>
        <Sider width={200} style={{ background: isDark ? '#141414' : '#fff' }}
          breakpoint="lg" collapsedWidth={0}>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            style={{ height: '100%', borderRight: 0, paddingTop: 8 }}
            theme={isDark ? 'dark' : 'light'}
          />
        </Sider>
        <Content style={{ padding: 24, background: isDark ? '#1a1a1a' : '#f5f5f5', overflow: 'auto' }}>
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/knowledge" element={<KnowledgePage />} />
                <Route path="/quiz" element={<QuizPage />} />
                <Route path="/flashcards" element={<FlashcardPage />} />
                <Route path="/game" element={<GamePage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/pipeline" element={<PipelinePage />} />
                <Route path="/study" element={<StudyPage />} />
                <Route path="/share" element={<SharePage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </Content>
      </Layout>
    </Layout>
  )
}
