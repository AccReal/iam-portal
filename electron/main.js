const { app, BrowserWindow, Menu, Tray, nativeImage, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const sessionStore = require(
  app.isPackaged
    ? path.join(__dirname, 'demo-apps/shared/session-store')
    : path.join(__dirname, '../demo-apps/shared/session-store')
);

const APP_EXE_MAP = {
  '20000000-0000-0000-0000-000000000001': 'demo-apps/crm-app/dist/win-unpacked/CRM Система.exe',
  '20000000-0000-0000-0000-000000000002': 'demo-apps/mail-app/dist/win-unpacked/Корпоративная почта.exe',
  '20000000-0000-0000-0000-000000000003': 'demo-apps/1c-app/dist/win-unpacked/1С Бухгалтерия.exe',
  '20000000-0000-0000-0000-000000000004': 'demo-apps/warehouse-app/dist/win-unpacked/Склад.exe',
};

let mainWindow;
let tray;

// IPC bridge for the renderer (Vue frontend served at localhost:3000).
// The frontend invokes these after login/logout so the shared session
// file used by every demo-app on the machine stays in sync.
ipcMain.handle('iam:save-session', (_event, session) => {
  try {
    sessionStore.saveSession(session);
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
});

ipcMain.handle('iam:clear-session', () => {
  sessionStore.clearSession();
  return { ok: true };
});

ipcMain.handle('iam:load-session', () => {
  return sessionStore.loadSession();
});

ipcMain.handle('iam:launch-app', (_event, appId) => {
  const relExe = APP_EXE_MAP[appId];
  if (!relExe) {
    return { ok: false, error: `Unknown appId: ${appId}` };
  }
  const exePath = path.join(__dirname, '..', relExe);
  const child = spawn(exePath, [], { detached: true, stdio: 'ignore' });
  child.unref();
  return { ok: true };
});

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: 'IAM System',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
      preload: path.join(__dirname, 'preload.js')
    },
    backgroundColor: '#ffffff',
    show: false
  });

  // Load the frontend URL
  mainWindow.loadURL('http://localhost:3000');

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Create application menu
  const template = [
    {
      label: 'Файл',
      submenu: [
        {
          label: 'Выход',
          accelerator: 'Alt+F4',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'Вид',
      submenu: [
        {
          label: 'Перезагрузить',
          accelerator: 'F5',
          click: () => {
            mainWindow.reload();
          }
        },
        {
          label: 'Полноэкранный режим',
          accelerator: 'F11',
          click: () => {
            mainWindow.setFullScreen(!mainWindow.isFullScreen());
          }
        },
        { type: 'separator' },
        {
          label: 'Инструменты разработчика',
          accelerator: 'F12',
          click: () => {
            mainWindow.webContents.toggleDevTools();
          }
        }
      ]
    },
    {
      label: 'Помощь',
      submenu: [
        {
          label: 'О программе',
          click: () => {
            const { dialog } = require('electron');
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'О программе',
              message: 'IAM System v1.0.0',
              detail: 'Система управления идентификацией и доступом\n\n© 2026 Your Company'
            });
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);

  // Handle window close
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  // Create tray icon - use smaller icon for tray
  const trayIconPath = path.join(__dirname, 'tray-icon.png');
  const fallbackIconPath = path.join(__dirname, 'icon.png');
  
  // Try to use tray-specific icon, fallback to main icon
  let iconPath = trayIconPath;
  try {
    require('fs').accessSync(trayIconPath);
  } catch {
    iconPath = fallbackIconPath;
  }
  
  const trayIcon = nativeImage.createFromPath(iconPath);
  tray = new Tray(trayIcon.resize({ width: 16, height: 16 }));

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Показать',
      click: () => {
        mainWindow.show();
      }
    },
    {
      label: 'Выход',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('IAM System');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    mainWindow.show();
  });
}

app.whenReady().then(() => {
  createWindow();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
});
