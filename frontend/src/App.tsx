import { Suspense, lazy, useState, useEffect } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Layout, Menu, Button, Spin, Drawer, Grid, Space } from 'antd'
import { FileTextOutlined, ApartmentOutlined, FormOutlined, IdcardOutlined, RobotOutlined, SettingOutlined, BulbOutlined, DashboardOutlined, PlayCircleOutlined, ScheduleOutlined, ShareAltOutlined, SearchOutlined, UserOutlined, MenuOutlined, LogoutOutlined } from '@ant-design/icons'
import { useTheme } from './components/ThemeProvider'
import ErrorBoundary from './components/ErrorBoundary'
import LoginPage from './pages/LoginPage'
import { useAuthStore } from './stores'

// Lazy-load all pages for code splitting
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const UploadPage = lazy(() => import('./pages/UploadPage'))
const KnowledgePage = lazy(() => import('./pages/KnowledgePage'))
const QuizPage = lazy(() => import('./pages/QuizPage'))
const FlashcardPage = lazy(() => import('./pages/FlashcardPage'))
const GamePage = lazy(() => import('./pages/GamePage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const StudyPage = lazy(() => import('./pages/StudyPage'))
const SharePage = lazy(() => import('./pages/SharePage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const PersonalCenterPage = lazy(() => import('./pages/PersonalCenterPage'))
const ReadingPage = lazy(() => import('./pages/ReadingPage'))
const SummaryPage = lazy(() => import('./pages/SummaryPage'))
const MindMapPage = lazy(() => import('./pages/MindMapPage'))
const InteractiveQuizPage = lazy(() => import('./pages/InteractiveQuizPage'))
const CoverageReportPage = lazy(() => import('./pages/CoverageReportPage'))

const { Header, Sider, Content } = Layout
const { useBreakpoint } = Grid

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
  const screens = useBreakpoint()
  const isMobile = !screens.lg
  const [drawerOpen, setDrawerOpen] = useState(false)
  const selectedKey = '/' + location.pathname.split('/')[1] || '/'

  // Auth
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)
  const user = useAuthStore(s => s.user)
  const logout = useAuthStore(s => s.logout)
  const restore = useAuthStore(s => s.restore)
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => { restore(); setAuthReady(true) }, [])

  // Close the mobile drawer whenever the route changes
  useEffect(() => { setDrawerOpen(false) }, [location.pathname])

  if (!authReady) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><Spin size="large" /></div>
  }

  if (!isAuthenticated) {
    return <LoginPage />
  }

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: <Link to="/">学习仪表盘</Link> },
    { type: 'group', label: '知识中枢', children: [
      { key: '/upload', icon: <FileTextOutlined />, label: <Link to="/upload">资料导入</Link> },
      { key: '/knowledge', icon: <ApartmentOutlined />, label: <Link to="/knowledge">思维导图</Link> },
    ]},
    { type: 'group', label: '深度学习', children: [
      { key: '/quiz', icon: <FormOutlined />, label: <Link to="/quiz">题库练习</Link> },
      { key: '/flashcards', icon: <IdcardOutlined />, label: <Link to="/flashcards">记忆闪卡</Link> },
      { key: '/study', icon: <ScheduleOutlined />, label: <Link to="/study">学习计划</Link> },
    ]},
    { type: 'group', label: '工具', children: [
      { key: '/search', icon: <SearchOutlined />, label: <Link to="/search">搜索</Link> },
      { key: '/chat', icon: <RobotOutlined />, label: <Link to="/chat">AI 对话</Link> },
      { key: '/game', icon: <PlayCircleOutlined />, label: <Link to="/game">互动游戏</Link> },
    ]},
    { type: 'group', label: '其他', children: [
      { key: '/share', icon: <ShareAltOutlined />, label: <Link to="/share">分享协作</Link> },
      { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">设置</Link> },
      { key: '/personal', icon: <UserOutlined />, label: <Link to="/personal">个人中心</Link> },
    ]},
  ]

  const menu = (
    <Menu
      mode="inline"
      selectedKeys={[selectedKey]}
      items={menuItems as any}
      style={{ height: '100%', borderRight: 0, paddingTop: 8 }}
      theme={isDark ? 'dark' : 'light'}
    />
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: isMobile ? '0 16px' : '0 24px', background: 'linear-gradient(90deg, #4f46e5 0%, #6366f1 100%)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {isMobile && (
            <Button type="text" icon={<MenuOutlined />} onClick={() => setDrawerOpen(true)}
              style={{ color: '#fff', fontSize: 18 }} aria-label="打开菜单" />
          )}
          <h1 style={{ color: '#fff', margin: 0, fontSize: 20, fontWeight: 700, whiteSpace: 'nowrap' }}>
            KnowAll Studio
          </h1>
        </div>
        <Space size="middle">
          <span style={{ color: 'rgba(255,255,255,0.9)', fontSize: 14 }}>{user?.username}</span>
          <Button type="text" icon={<BulbOutlined />} onClick={toggle}
            style={{ color: '#fff', fontSize: 18 }}
            title={isDark ? '浅色模式' : '深色模式'} />
          <Button type="text" icon={<LogoutOutlined />} onClick={logout}
            style={{ color: '#fff' }} title="登出" />
        </Space>
      </Header>
      <Layout>
        {isMobile ? (
          <Drawer
            placement="left"
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            width={220}
            styles={{ body: { padding: 0 }, header: { display: 'none' } }}
            className={isDark ? 'app-drawer-dark' : undefined}
          >
            {menu}
          </Drawer>
        ) : (
          <Sider width={200} theme={isDark ? 'dark' : 'light'}>
            {menu}
          </Sider>
        )}
        <Content style={{ padding: isMobile ? 12 : 24, overflow: 'auto' }}>
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <div className="page-fade" key={location.pathname}>
                <Routes>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/upload" element={<UploadPage />} />
                  <Route path="/knowledge" element={<KnowledgePage />} />
                  <Route path="/search" element={<SearchPage />} />
                  <Route path="/quiz" element={<QuizPage />} />
                  <Route path="/flashcards" element={<FlashcardPage />} />
                  <Route path="/game" element={<GamePage />} />
                  <Route path="/chat" element={<ChatPage />} />
                  <Route path="/study" element={<StudyPage />} />
                  <Route path="/share" element={<SharePage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/personal" element={<PersonalCenterPage />} />
                  <Route path="/reading" element={<ReadingPage />} />
                  <Route path="/summary/:id" element={<SummaryPage />} />
                  <Route path="/mindmap/:summaryId" element={<MindMapPage />} />
                  <Route path="/quiz/interactive/:summaryId" element={<InteractiveQuizPage />} />
                  <Route path="/coverage/:summaryId" element={<CoverageReportPage />} />
                </Routes>
              </div>
            </Suspense>
          </ErrorBoundary>
        </Content>
      </Layout>
    </Layout>
  )
}
