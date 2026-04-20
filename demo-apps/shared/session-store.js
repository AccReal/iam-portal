/**
 * Shared session store for IAM Portal desktop ecosystem.
 *
 * Writes a single JSON file that the IAM Portal Electron shell and every
 * demo-app read/write. That is how we get the SSO UX: one login in the
 * Portal unlocks every desktop app on the machine — exactly like real
 * corporate SSO, just without a central server for the desktop itself.
 *
 * File layout:
 *   %APPDATA%/IAMPortal/session.json                   (Windows)
 *   ~/Library/Application Support/IAMPortal/session.json (macOS)
 *   ~/.config/IAMPortal/session.json                   (Linux)
 *
 * Contents:
 *   { access_token, refresh_token, user, saved_at }
 *
 * Security note: this file holds JWTs in plain text under the user's
 * profile directory. On Windows that's already ACL-scoped to the current
 * user. We set 0600 on POSIX. This is adequate for a diploma demo; a
 * production build would use the OS keychain (keytar / Credential Manager).
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');

const APP_DIR_NAME = 'IAMPortal';
const FILE_NAME = 'session.json';

function getSessionDir() {
  if (process.platform === 'win32') {
    return path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'), APP_DIR_NAME);
  }
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', APP_DIR_NAME);
  }
  return path.join(process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'), APP_DIR_NAME);
}

function getSessionPath() {
  return path.join(getSessionDir(), FILE_NAME);
}

function ensureDir() {
  const dir = getSessionDir();
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function loadSession() {
  try {
    const p = getSessionPath();
    if (!fs.existsSync(p)) return null;
    const raw = fs.readFileSync(p, 'utf8');
    if (!raw.trim()) return null;
    const parsed = JSON.parse(raw);
    if (!parsed.access_token) return null;
    return parsed;
  } catch (err) {
    console.error('[session-store] load failed:', err.message);
    return null;
  }
}

function saveSession(session) {
  if (!session || !session.access_token) {
    throw new Error('saveSession: access_token is required');
  }
  ensureDir();
  const p = getSessionPath();
  const payload = {
    access_token: session.access_token,
    refresh_token: session.refresh_token || null,
    user: session.user || null,
    saved_at: new Date().toISOString(),
  };
  const tmp = p + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(payload, null, 2), { encoding: 'utf8' });
  fs.renameSync(tmp, p);
  if (process.platform !== 'win32') {
    try { fs.chmodSync(p, 0o600); } catch (_) { /* best-effort */ }
  }
  return payload;
}

function clearSession() {
  try {
    const p = getSessionPath();
    if (fs.existsSync(p)) fs.unlinkSync(p);
  } catch (err) {
    console.error('[session-store] clear failed:', err.message);
  }
}

/**
 * Watch the session file for changes. Fires 'change' when the file is
 * created, modified, or removed. Demo-apps use this so that a login inside
 * IAM Portal instantly unlocks already-open app windows.
 */
function watchSession() {
  ensureDir();
  const emitter = new EventEmitter();
  const dir = getSessionDir();
  let watcher = null;
  try {
    watcher = fs.watch(dir, { persistent: false }, (_event, filename) => {
      if (filename === FILE_NAME) {
        emitter.emit('change', loadSession());
      }
    });
  } catch (err) {
    console.error('[session-store] watch failed:', err.message);
  }
  emitter.close = () => { if (watcher) watcher.close(); };
  return emitter;
}

module.exports = {
  getSessionPath,
  loadSession,
  saveSession,
  clearSession,
  watchSession,
};
