const { app, BrowserWindow, shell, ipcMain } = require('electron')
const path = require('path')
const { spawn, execSync } = require('child_process')
const http = require('http')

let mainWindow = null
let backendProcess = null

// Try to find python (python3 or python)
function findPython() {
  try {
    execSync('python --version', { stdio: 'ignore' })
    return 'python'
  } catch {
    try {
      execSync('python3 --version', { stdio: 'ignore' })
      return 'python3'
    } catch {
      return null
    }
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    title: 'KnowAll Studio',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,  // Don't show until ready
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  const isDev = process.env.NODE_ENV === 'development'
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../frontend/dist/index.html'))
  }

  mainWindow.on('closed', () => { mainWindow = null })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

function startBackend() {
  const pythonCmd = findPython()
  if (!pythonCmd) {
    console.error('Python not found. Please install Python 3.11+ from https://python.org')
    return false
  }

  const backendPath = path.join(__dirname, '../backend')
  const isDev = process.env.NODE_ENV === 'development'

  const args = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000']
  if (isDev) args.push('--reload')

  backendProcess = spawn(pythonCmd, args, {
    cwd: backendPath,
    stdio: 'pipe',
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  })

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data}`)
  })

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error] ${data}`)
  })

  backendProcess.on('error', (err) => {
    console.error(`Failed to start backend: ${err.message}`)
  })

  backendProcess.on('close', (code) => {
    console.log(`Backend process exited with code ${code}`)
    backendProcess = null
  })

  return true
}

function stopBackend() {
  if (backendProcess) {
    if (process.platform === 'win32') {
      // Windows: kill the entire process tree
      try {
        execSync(`taskkill /pid ${backendProcess.pid} /T /F`, { stdio: 'ignore' })
      } catch { /* process may already be dead */ }
    } else {
      backendProcess.kill('SIGTERM')
      // Force kill after 5s if still alive
      setTimeout(() => {
        if (backendProcess) {
          try { backendProcess.kill('SIGKILL') } catch {}
        }
      }, 5000)
    }
    backendProcess = null
  }
}

function waitForBackend(maxRetries = 30, interval = 1000) {
  return new Promise((resolve) => {
    let attempts = 0
    function check() {
      attempts++
      const req = http.get('http://127.0.0.1:8000/health', (res) => {
        if (res.statusCode === 200) {
          resolve(true)
        } else if (attempts < maxRetries) {
          setTimeout(check, interval)
        } else {
          resolve(false)
        }
      })
      req.on('error', () => {
        if (attempts < maxRetries) {
          setTimeout(check, interval)
        } else {
          resolve(false)
        }
      })
      req.setTimeout(2000, () => {
        req.destroy()
        if (attempts < maxRetries) {
          setTimeout(check, interval)
        } else {
          resolve(false)
        }
      })
    }
    check()
  })
}

// IPC handlers
ipcMain.handle('select-file', async () => {
  const { dialog } = require('electron')
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Documents', extensions: ['pdf', 'docx', 'pptx', 'md', 'txt', 'xlsx', 'xmind'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  })
  return result.canceled ? null : result.filePaths[0]
})

ipcMain.handle('select-directory', async () => {
  const { dialog } = require('electron')
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  })
  return result.canceled ? null : result.filePaths[0]
})

app.whenReady().then(async () => {
  const started = startBackend()
  if (!started) {
    // Create window anyway, backend error will show in UI
    createWindow()
    return
  }
  // Wait for backend health check, then show window
  const backendReady = await waitForBackend()
  if (!backendReady) {
    console.warn('Backend did not respond within timeout, showing window anyway')
  }
  createWindow()
})

app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

app.on('before-quit', () => {
  stopBackend()
})
