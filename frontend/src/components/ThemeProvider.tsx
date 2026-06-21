import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { ConfigProvider, theme as antTheme } from 'antd'

interface ThemeContextType {
  isDark: boolean
  toggle: () => void
}

const ThemeContext = createContext<ThemeContextType>({ isDark: false, toggle: () => {} })

export function useTheme() {
  return useContext(ThemeContext)
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [isDark, setIsDark] = useState(() => {
    const stored = localStorage.getItem('knowall-theme')
    return stored === 'dark'
  })

  useEffect(() => {
    localStorage.setItem('knowall-theme', isDark ? 'dark' : 'light')
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
  }, [isDark])

  const toggle = () => setIsDark(v => !v)

  return (
    <ThemeContext.Provider value={{ isDark, toggle }}>
      <ConfigProvider theme={{
        algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
        token: { colorPrimary: '#4f46e5', borderRadius: 8 },
      }}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}
