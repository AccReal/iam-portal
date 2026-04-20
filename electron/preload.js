/**
 * Preload for the IAM Portal Electron shell.
 *
 * Exposes a tiny, purpose-built bridge to the Vue frontend so that after a
 * successful login/registration/MFA verification the frontend can hand the
 * freshly issued JWT pair over to the desktop side, which persists it into
 * the shared session file consumed by every demo-app on this machine.
 *
 * Why not use localStorage? Because localStorage is per-origin and per-
 * BrowserWindow — the CRM exe cannot read what the Portal window wrote. A
 * file under %APPDATA%/IAMPortal is the only thing they all agree on.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('iamDesktop', {
  // Feature flag the frontend checks to decide whether to push sessions.
  isDesktop: true,

  // Persist the tokens + user profile to the shared session store.
  // Returns a promise that resolves to { ok: true } or { ok: false, error }.
  saveSession: (session) => ipcRenderer.invoke('iam:save-session', session),

  // Called on logout — wipes the shared session so demo-apps fall back to
  // the "please log in via Portal" screen.
  clearSession: () => ipcRenderer.invoke('iam:clear-session'),

  // Read the current session (used on app start to avoid a re-login loop
  // when the Portal is reopened while demo-apps already have a session).
  loadSession: () => ipcRenderer.invoke('iam:load-session'),

  // Launch a demo-app exe by its UUID. Returns { ok: true } or { ok: false, error }.
  launchApp: (appId) => ipcRenderer.invoke('iam:launch-app', appId),
});
