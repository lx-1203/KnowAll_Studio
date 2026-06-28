import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, App as AntdApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { ThemeProvider } from './components/ThemeProvider'
import App from './App'
import './index.css'

// 抑制 antd 内部 findDOMNode 警告（React 18 + antd 5.18 兼容问题，第三方库无法修复）
const originalError = console.error
console.error = (...args: any[]) => {
  if (typeof args[0] === 'string' && args[0].includes('findDOMNode')) return
  originalError.apply(console, args)
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ConfigProvider locale={zhCN}>
    <AntdApp>
      <ThemeProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <App />
        </BrowserRouter>
      </ThemeProvider>
    </AntdApp>
  </ConfigProvider>
)
