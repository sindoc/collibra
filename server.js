#!/usr/bin/env node
'use strict';

/**
 * Message Broker Gateway — API v1.0
 *
 * Routes:
 *   POST   /api/1.0/onboard                    Register a new client → { clientId, token }
 *   GET    /api/1.0/status                      Health + stats (auth required)
 *   GET    /api/1.0/topics                      List all topics     (auth required)
 *   POST   /api/1.0/topics                      Register a topic    (auth required)
 *   DELETE /api/1.0/topics/:topic               Deregister a topic  (auth required, owner only)
 *   POST   /api/1.0/topics/:topic/publish       Publish a message   (auth required)
 *   GET    /api/1.0/topics/:topic/subscribe     Subscribe via SSE   (auth required)
 *
 * Virtual host static serving:
 *   Requests to any other path are served from ./<hostname>/ if the directory exists,
 *   falling back to ./www/.
 *
 * Usage:
 *   node server.js [--port 443] [--key /path/key.pem] [--cert /path/cert.pem]
 *   node server.js --port 8080          # plain HTTP (no TLS)
 */

const https  = require('https');
const http   = require('http');
const fs     = require('fs');
const path   = require('path');
const crypto = require('crypto');
const url    = require('url');

// ── CLI args ──────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) { out[argv[i].slice(2)] = argv[i + 1] || true; i++; }
  }
  return out;
}

const args     = parseArgs(process.argv.slice(2));
const PORT     = parseInt(args.port  || process.env.PORT     || 8080, 10);
const KEY_FILE = args.key  || process.env.TLS_KEY  || null;
const CERT_FILE= args.cert || process.env.TLS_CERT || null;
const BASE_DIR = __dirname;
const API_VER  = '1.0';
const API_PFX  = `/api/${API_VER}`;

// ── In-memory state ───────────────────────────────────────────────────────────

/** topic name → { name, owner, metadata, subscribers: Set<res>, buffer: msg[] } */
const topics  = new Map();

/** clientId → { id, name, host, token, registeredAt, subscriptions: Set<topic> } */
const clients = new Map();

// ── Logging ───────────────────────────────────────────────────────────────────

function log(level, msg, meta = {}) {
  process.stdout.write(JSON.stringify({ ts: new Date().toISOString(), level, msg, ...meta }) + '\n');
}

// ── Domain logic: onboarding ──────────────────────────────────────────────────

function onboard(body) {
  const { name, host } = body;
  if (!name) return [400, { error: 'name_required' }];
  const id    = crypto.randomUUID();
  const token = crypto.randomBytes(32).toString('hex');
  clients.set(id, { id, name, host: host || 'unknown', token, registeredAt: new Date().toISOString(), subscriptions: new Set() });
  log('info', 'client onboarded', { id, name });
  return [200, { ok: true, clientId: id, token, apiBase: API_PFX }];
}

// ── Domain logic: topics ──────────────────────────────────────────────────────

function topicRegister(client, body) {
  const { name, metadata = {} } = body;
  if (!name)          return [400, { error: 'name_required' }];
  if (topics.has(name)) return [409, { error: 'topic_exists' }];
  topics.set(name, { name, owner: client.id, metadata, subscribers: new Set(), buffer: [], createdAt: new Date().toISOString() });
  log('info', 'topic registered', { topic: name, owner: client.id });
  return [200, { ok: true, topic: name }];
}

function topicDeregister(client, topicName) {
  const t = topics.get(topicName);
  if (!t)                   return [404, { error: 'not_found' }];
  if (t.owner !== client.id) return [403, { error: 'forbidden' }];
  for (const res of t.subscribers) { sendEvent(res, 'teardown', { topic: topicName }); res.end(); }
  topics.delete(topicName);
  log('info', 'topic deregistered', { topic: topicName });
  return [200, { ok: true }];
}

function topicList() {
  const list = [...topics.values()].map(({ name, owner, metadata, createdAt }) => ({ name, owner, metadata, createdAt }));
  return [200, { topics: list }];
}

// ── Domain logic: publish ─────────────────────────────────────────────────────

function publish(client, topicName, payload) {
  const t = topics.get(topicName);
  if (!t) return [404, { error: 'topic_not_found' }];
  const msg = { id: crypto.randomUUID(), topic: topicName, from: client.id, payload, ts: new Date().toISOString() };
  let delivered = 0;
  for (const res of t.subscribers) { sendEvent(res, 'message', msg); delivered++; }
  t.buffer.push(msg);
  if (t.buffer.length > 200) t.buffer.shift();   // ring-buffer cap
  log('info', 'published', { topic: topicName, msgId: msg.id, delivered });
  return [200, { ok: true, msgId: msg.id, delivered }];
}

// ── SSE helpers ───────────────────────────────────────────────────────────────

function initSSE(res) {
  res.writeHead(200, {
    'Content-Type':                'text/event-stream',
    'Cache-Control':               'no-cache',
    'Connection':                  'keep-alive',
    'Access-Control-Allow-Origin': '*',
  });
  res.write(': connected\n\n');
}

function sendEvent(res, event, data) {
  try { res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`); } catch (_) { /* gone */ }
}

// ── Subscribe (SSE) ───────────────────────────────────────────────────────────

function subscribe(req, res, client, topicName) {
  const t = topics.get(topicName);
  if (!t) return respond(res, 404, { error: 'topic_not_found' });
  initSSE(res);
  t.subscribers.add(res);
  client.subscriptions.add(topicName);
  log('info', 'subscribed', { clientId: client.id, topic: topicName });
  // Replay buffered messages so the subscriber catches up
  for (const msg of t.buffer) sendEvent(res, 'message', msg);
  req.on('close', () => {
    t.subscribers.delete(res);
    client.subscriptions.delete(topicName);
    log('info', 'unsubscribed', { clientId: client.id, topic: topicName });
  });
}

// ── HTTP helpers ──────────────────────────────────────────────────────────────

const CORS_HEADERS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization,Content-Type',
};

function respond(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, { 'Content-Type': 'application/json', ...CORS_HEADERS });
  res.end(payload);
}

function readJSON(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      try   { resolve(JSON.parse(Buffer.concat(chunks).toString() || '{}')); }
      catch (_) { resolve({}); }
    });
    req.on('error', reject);
  });
}

function bearerToken(req) {
  return (req.headers['authorization'] || '').replace(/^Bearer\s+/i, '');
}

function authenticate(req) {
  const token = bearerToken(req);
  if (!token) return null;
  for (const c of clients.values()) if (c.token === token) return c;
  return null;
}

// ── API router ────────────────────────────────────────────────────────────────

async function handleAPI(req, res) {
  const { pathname } = url.parse(req.url);
  const method = req.method.toUpperCase();

  // CORS preflight
  if (method === 'OPTIONS') {
    res.writeHead(204, CORS_HEADERS);
    return res.end();
  }

  // Strip prefix: /api/1.0/topics/foo/publish → ['topics', 'foo', 'publish']
  const segments = pathname.slice(API_PFX.length).replace(/^\//, '').split('/').filter(Boolean);
  const [seg0, seg1, seg2] = segments;

  // ── POST /api/1.0/onboard  (public — no auth) ────────────────────────────
  if (method === 'POST' && seg0 === 'onboard') {
    const body = await readJSON(req);
    const [status, result] = onboard(body);
    return respond(res, status, result);
  }

  // ── All other routes require a valid Bearer token ────────────────────────
  const client = authenticate(req);
  if (!client) return respond(res, 401, { error: 'unauthorized', hint: 'POST /api/1.0/onboard to register' });

  // ── GET /api/1.0/status ──────────────────────────────────────────────────
  if (method === 'GET' && seg0 === 'status') {
    return respond(res, 200, { ok: true, version: API_VER, topics: topics.size, clients: clients.size, uptime: Math.floor(process.uptime()) });
  }

  // ── GET /api/1.0/topics ──────────────────────────────────────────────────
  if (method === 'GET' && seg0 === 'topics' && !seg1) {
    const [status, result] = topicList();
    return respond(res, status, result);
  }

  // ── POST /api/1.0/topics ─────────────────────────────────────────────────
  if (method === 'POST' && seg0 === 'topics' && !seg1) {
    const body = await readJSON(req);
    const [status, result] = topicRegister(client, body);
    return respond(res, status, result);
  }

  // ── DELETE /api/1.0/topics/:topic ────────────────────────────────────────
  if (method === 'DELETE' && seg0 === 'topics' && seg1 && !seg2) {
    const [status, result] = topicDeregister(client, decodeURIComponent(seg1));
    return respond(res, status, result);
  }

  // ── POST /api/1.0/topics/:topic/publish ──────────────────────────────────
  if (method === 'POST' && seg0 === 'topics' && seg2 === 'publish') {
    const body = await readJSON(req);
    const [status, result] = publish(client, decodeURIComponent(seg1), body.payload);
    return respond(res, status, result);
  }

  // ── GET /api/1.0/topics/:topic/subscribe  (SSE long-poll) ────────────────
  if (method === 'GET' && seg0 === 'topics' && seg2 === 'subscribe') {
    return subscribe(req, res, client, decodeURIComponent(seg1));
  }

  return respond(res, 404, { error: 'route_not_found', path: pathname });
}

// ── Virtual-host static file server ─────────────────────────────────────────

const MIME_TYPES = {
  '.html': 'text/html',          '.js':   'application/javascript',
  '.css':  'text/css',           '.json': 'application/json',
  '.png':  'image/png',          '.jpg':  'image/jpeg',
  '.svg':  'image/svg+xml',      '.ico':  'image/x-icon',
  '.woff2':'font/woff2',         '.woff': 'font/woff',
};

function resolveVhostDir(hostname) {
  const host = (hostname || '').split(':')[0];                          // strip port
  const exact = path.join(BASE_DIR, host);
  if (fs.existsSync(exact) && fs.statSync(exact).isDirectory()) return exact;
  const www = path.join(BASE_DIR, 'www');
  if (fs.existsSync(www)   && fs.statSync(www).isDirectory())   return www;
  return null;
}

function serveStatic(req, res, vhostDir) {
  const { pathname } = url.parse(req.url);
  const relative     = pathname === '/' ? 'index.html' : pathname;
  const filePath     = path.resolve(vhostDir, '.' + relative);

  // Path-traversal guard
  if (!filePath.startsWith(path.resolve(vhostDir))) {
    return respond(res, 403, { error: 'forbidden' });
  }

  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) return respond(res, 404, { error: 'not_found' });
    const mime = MIME_TYPES[path.extname(filePath)] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': mime });
    fs.createReadStream(filePath).pipe(res);
  });
}

// ── Main request handler ─────────────────────────────────────────────────────

async function requestHandler(req, res) {
  const { pathname } = url.parse(req.url);
  log('debug', 'request', { method: req.method, host: req.headers.host, path: pathname });

  // API gateway
  if (pathname.startsWith(API_PFX + '/') || pathname === API_PFX) {
    return handleAPI(req, res).catch(err => {
      log('error', 'api_error', { err: err.message });
      respond(res, 500, { error: 'internal_server_error' });
    });
  }

  // Virtual-host static serving
  const vhostDir = resolveVhostDir(req.headers.host);
  if (vhostDir) return serveStatic(req, res, vhostDir);

  respond(res, 404, { error: 'no_vhost', host: req.headers.host });
}

// ── Start ─────────────────────────────────────────────────────────────────────

function start() {
  const useTLS = KEY_FILE && CERT_FILE;

  if (useTLS) {
    const tlsOptions = { key: fs.readFileSync(KEY_FILE), cert: fs.readFileSync(CERT_FILE) };
    https.createServer(tlsOptions, requestHandler).listen(PORT, () =>
      log('info', 'HTTPS broker started', { port: PORT, api: API_PFX }));

    // HTTP → HTTPS redirect
    http.createServer((req, res) => {
      const host = (req.headers.host || '').split(':')[0];
      res.writeHead(301, { Location: `https://${host}${PORT === 443 ? '' : ':' + PORT}${req.url}` });
      res.end();
    }).listen(80, () => log('info', 'HTTP→HTTPS redirect on :80'));

  } else {
    http.createServer(requestHandler).listen(PORT, () =>
      log('info', 'HTTP broker started', { port: PORT, api: API_PFX }));
  }
}

start();
