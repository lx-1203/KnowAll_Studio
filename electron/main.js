const { app, BrowserWindow, shell, ipcMain } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let mainWindow = null
let backendProcess = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    title: '智识工坊 - KnowAll Studio',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // In development, load from Vite dev server; in production, load built files
  const isDev = process.env.NODE_ENV === 'development'
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../frontend/dist/index.html'))
  }

  mainWindow.on('closed', () => { mainWindow = null })

  // Open external links in browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

function startBackend() {
  // Start the FastAPI backend process
  const backendPath = path.join(__dirname, '../backend')
  const isDev = process.env.NODE_ENV === 'development'

  const args = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000']
  if (isDev) args.push('--reload')

  backendProcess = spawn('python', args, {
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

  backendProcess.on('close', (code) => {
    console.log(`Backend process exited with code ${code}`)
  })
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
}

// IPC handlers for native dialogs
ipcMain.handle('select-file', async () => {
  const { dialog } = require('electron')
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Documents', extensions: ['pdf', 'docx', 'pptx', 'md', 'txt'] },
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

app.whenReady().then(() => {
  startBackend()
  // Give backend a moment to start
  setTimeout(createWindow, 2000)
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
