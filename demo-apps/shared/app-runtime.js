/**
 * Generic Electron runtime reused by every demo-app (1C, CRM, Mail, Warehouse).
 *
 * Keeps main.js of each app trivial: pick an APP_ID and a window title,
 * this module handles the whole "login via IAM Portal → check access →
 * show app / show denied / show login-prompt" flow, plus auto-reload on
 * session changes so that logging into the Portal unlocks any already-open
 * demo-app window without a relaunch.
 */

const { app, BrowserWindow, shell, ipcMain } = require('electron');
const path = require('path');

const iamClient = require('./iam-client');
const sessionStore = require('./session-store');

function createRuntime(options) {
  const {
    appId,                                   // UUID from seed.py
    title,                                   // Window title
    iconPath,                                // Absolute path to icon.png
    appDir,                                  // Absolute path to the demo-app folder
    portalUrl = 'http://localhost:3000',     // IAM web portal
    backend = iamClient.DEFAULT_BACKEND,
  } = options;

  if (!appId || !appDir) throw new Error('createRuntime: appId and appDir are required');

  let currentWindow = null;
  let currentState = null;        // 'login-required' | 'granted' | 'denied' | 'backend-unreachable'
  let watcher = null;
  let reevaluating = false;

  function commonWebPreferences() {
    return {
      // Legacy HTML files in demo-apps use require() directly, so keep
      // nodeIntegration for now. Not a security concern: these apps only
      // load local HTML and only talk to localhost.
      nodeIntegration: true,
      contextIsolation: false,
    };
  }

  function closeCurrent() {
    if (currentWindow && !currentWindow.isDestroyed()) {
      currentWindow.removeAllListeners('closed');
      currentWindow.close();
    }
    currentWindow = null;
  }

  function showLoginPrompt() {
    currentState = 'login-required';
    closeCurrent();
    currentWindow = new BrowserWindow({
      width: 520, height: 420,
      title: `${title} — Требуется вход`,
      icon: iconPath,
      resizable: false,
      webPreferences: commonWebPreferences(),
    });
    // The shared login-prompt.html lives alongside this module.
    currentWindow.loadFile(path.join(__dirname, 'login-prompt.html'));
    currentWindow.webContents.on('did-finish-load', () => {
      currentWindow.webContents.send('prompt-info', { appTitle: title, portalUrl });
    });
    currentWindow.on('closed', () => { currentWindow = null; });
  }

  function showBackendUnreachable() {
    currentState = 'backend-unreachable';
    closeCurrent();
    currentWindow = new BrowserWindow({
      width: 520, height: 360,
      title: `${title} — Сервер недоступен`,
      icon: iconPath,
      resizable: false,
      webPreferences: commonWebPreferences(),
    });
    currentWindow.loadFile(path.join(__dirname, 'backend-down.html'));
    currentWindow.webContents.on('did-finish-load', () => {
      currentWindow.webContents.send('prompt-info', { appTitle: title, backend });
    });
    currentWindow.on('closed', () => { currentWindow = null; });
  }

  function showAccessDenied(user, reason) {
    currentState = 'denied';
    closeCurrent();
    currentWindow = new BrowserWindow({
      width: 600, height: 460,
      title: `${title} — Доступ запрещён`,
      icon: iconPath,
      resizable: false,
      webPreferences: commonWebPreferences(),
    });
    currentWindow.loadFile(path.join(__dirname, 'access-denied.html'));
    currentWindow.webContents.on('did-finish-load', () => {
      currentWindow.webContents.send('user-info', { ...user, appTitle: title, denyReason: reason });
    });
    currentWindow.on('closed', () => { currentWindow = null; });
  }

  function showApp(user) {
    currentState = 'granted';
    closeCurrent();
    currentWindow = new BrowserWindow({
      width: 1400, height: 900,
      title, icon: iconPath,
      webPreferences: commonWebPreferences(),
    });
    currentWindow.loadFile(path.join(appDir, 'app.html'));
    currentWindow.webContents.on('did-finish-load', () => {
      currentWindow.webContents.send('user-info', user);
    });
    currentWindow.on('closed', () => { currentWindow = null; });
  }

  async function evaluate() {
    if (reevaluating) return;
    reevaluating = true;
    try {
      const result = await iamClient.checkLaunch(appId, backend);
      if (result.state === 'granted') {
        if (currentState !== 'granted') showApp(result.user);
      } else if (result.state === 'denied') {
        if (currentState !== 'denied') showAccessDenied(result.user, result.reason);
      } else if (result.state === 'backend-unreachable') {
        if (currentState !== 'backend-unreachable') showBackendUnreachable();
      } else {
        if (currentState !== 'login-required') showLoginPrompt();
      }
    } finally {
      reevaluating = false;
    }
  }

  // IPC handlers used by login-prompt.html / backend-down.html.
  ipcMain.on('iam:open-portal', () => shell.openExternal(portalUrl));
  ipcMain.on('iam:recheck', () => evaluate());
  ipcMain.on('iam:quit', () => app.quit());

  app.whenReady().then(async () => {
    await evaluate();
    // React to login/logout in IAM Portal or any other demo-app.
    watcher = sessionStore.watchSession();
    watcher.on('change', () => {
      // Debounce: the OS often fires two events for a single write.
      setTimeout(() => evaluate(), 150);
    });
    // Periodic recheck so an expired access token is caught even when the
    // session file hasn't changed (token TTL runs out while app is open).
    setInterval(() => evaluate(), 5 * 60 * 1000);
  });

  app.on('window-all-closed', () => {
    if (watcher) watcher.close();
    app.quit();
  });
}

module.exports = { createRuntime };
