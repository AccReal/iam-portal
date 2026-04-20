/**
 * Thin HTTP client used by every demo-app to talk to the IAM backend.
 *
 * Responsibilities:
 *   - Validate the cached access_token via /auth/me
 *   - Automatically rotate the pair through /auth/refresh on 401
 *   - Check per-application access via /sso/check-access
 *
 * We intentionally use the built-in `http` module (no axios/node-fetch) so
 * the demo-apps don't need extra dependencies. Payloads are tiny anyway.
 */

const http = require('http');
const sessionStore = require('./session-store');

const DEFAULT_BACKEND = 'http://localhost:8000';

function parseUrl(base) {
  const u = new URL(base);
  return {
    hostname: u.hostname,
    port: u.port ? Number(u.port) : (u.protocol === 'https:' ? 443 : 80),
  };
}

function request(method, base, path, { token, body } = {}) {
  const { hostname, port } = parseUrl(base);
  const payload = body ? JSON.stringify(body) : null;

  const options = {
    hostname, port, path, method,
    headers: {
      'Accept': 'application/json',
    },
  };
  if (token) options.headers['Authorization'] = `Bearer ${token}`;
  if (payload) {
    options.headers['Content-Type'] = 'application/json';
    options.headers['Content-Length'] = Buffer.byteLength(payload);
  }

  return new Promise((resolve) => {
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        let json = null;
        try { json = data ? JSON.parse(data) : null; } catch (_) { json = null; }
        resolve({ status: res.statusCode || 0, body: json });
      });
    });
    req.on('error', (err) => resolve({ status: 0, body: null, error: err.message }));
    if (payload) req.write(payload);
    req.end();
  });
}

async function fetchMe(backend, token) {
  return request('GET', backend, '/api/v1/auth/me', { token });
}

async function refresh(backend, refreshToken) {
  return request('POST', backend, '/api/v1/auth/refresh', {
    body: { refresh_token: refreshToken },
  });
}

async function checkAccess(backend, token, appId) {
  return request('GET', backend, `/api/v1/sso/check-access?app_id=${encodeURIComponent(appId)}`, { token });
}

/**
 * Resolve the current authenticated user, transparently rotating the
 * token pair when the access token has expired.
 *
 * Returns one of:
 *   { status: 'ok',            session, user }
 *   { status: 'no-session' }                         — no cached tokens
 *   { status: 'unauthenticated' }                    — tokens invalid/expired, refresh failed
 *   { status: 'backend-unreachable' }                — IAM server down
 */
async function resolveSession(backend = DEFAULT_BACKEND) {
  const session = sessionStore.loadSession();
  if (!session || !session.access_token) return { status: 'no-session' };

  let me = await fetchMe(backend, session.access_token);
  if (me.status === 0) return { status: 'backend-unreachable' };

  if (me.status === 401 && session.refresh_token) {
    const rot = await refresh(backend, session.refresh_token);
    if (rot.status === 0) return { status: 'backend-unreachable' };
    if (rot.status !== 200 || !rot.body || !rot.body.access_token) {
      sessionStore.clearSession();
      return { status: 'unauthenticated' };
    }
    const refreshed = {
      access_token: rot.body.access_token,
      refresh_token: rot.body.refresh_token || session.refresh_token,
      user: rot.body.user || session.user,
    };
    sessionStore.saveSession(refreshed);
    me = await fetchMe(backend, refreshed.access_token);
    if (me.status !== 200) {
      sessionStore.clearSession();
      return { status: 'unauthenticated' };
    }
    return { status: 'ok', session: refreshed, user: me.body };
  }

  if (me.status !== 200) {
    sessionStore.clearSession();
    return { status: 'unauthenticated' };
  }
  return { status: 'ok', session, user: me.body };
}

/**
 * Full launch-time check: is the user logged in AND allowed into this app?
 *
 * Result:
 *   { state: 'granted', user, permissions }
 *   { state: 'denied', user, reason }                — logged in but no rights
 *   { state: 'login-required' }                      — no valid session
 *   { state: 'backend-unreachable' }
 */
async function checkLaunch(appId, backend = DEFAULT_BACKEND) {
  const s = await resolveSession(backend);
  if (s.status === 'backend-unreachable') return { state: 'backend-unreachable' };
  if (s.status !== 'ok') return { state: 'login-required' };

  const acc = await checkAccess(backend, s.session.access_token, appId);
  if (acc.status === 0) return { state: 'backend-unreachable' };
  if (acc.status === 200 && acc.body && acc.body.granted) {
    return { state: 'granted', user: acc.body.user || s.user, permissions: acc.body.permissions };
  }
  if (acc.status === 403) {
    return { state: 'denied', user: s.user, reason: (acc.body && acc.body.detail) || 'Нет прав' };
  }
  if (acc.status === 401) return { state: 'login-required' };
  return { state: 'denied', user: s.user, reason: 'Неизвестная ошибка' };
}

module.exports = {
  DEFAULT_BACKEND,
  resolveSession,
  checkLaunch,
};
