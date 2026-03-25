// Export OKX CEX contract history (SWAP/FUTURES) into JSONL.
// Reads credentials from ~/.okx/config.toml (Agent Trade Kit profile format).
// No env OKX_* should be relied upon.

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

function parseArgs() {
  const args = process.argv.slice(2);
  const out = { profile: 'live', days: 90, outDir: '' };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--profile') out.profile = args[++i];
    else if (a === '--days') out.days = Number(args[++i]);
    else if (a === '--out') out.outDir = args[++i];
  }
  if (!out.outDir) throw new Error('Missing --out <dir>');
  return out;
}

const HOME = process.env.USERPROFILE || process.env.HOME;
const CONFIG_PATH = path.join(HOME, '.okx', 'config.toml');

function parseTomlProfiles(tomlText) {
  const lines = tomlText.split(/\r?\n/);
  let defaultProfile = 'default';
  const profiles = {};
  let cur = null;
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const mDef = line.match(/^default_profile\s*=\s*"([^"]+)"/);
    if (mDef) { defaultProfile = mDef[1]; continue; }
    const mProf = line.match(/^\[profiles\.(.+)\]$/);
    if (mProf) { cur = mProf[1]; profiles[cur] = profiles[cur] || {}; continue; }
    const mKV = line.match(/^([A-Za-z0-9_\-]+)\s*=\s*"?([^"#]+)"?$/);
    if (mKV && cur) {
      profiles[cur][mKV[1]] = mKV[2].trim();
    }
  }
  return { defaultProfile, profiles };
}

function loadProfile(name) {
  const toml = fs.readFileSync(CONFIG_PATH, 'utf8');
  const { defaultProfile, profiles } = parseTomlProfiles(toml);
  const p = profiles[name] || profiles[defaultProfile];
  if (!p) throw new Error(`Profile not found: ${name}`);
  const apiKey = p.api_key;
  const secretKey = p.secret_key;
  const passphrase = p.passphrase;
  const baseUrl = (p.base_url || 'https://www.okx.com').replace(/\/+$/, '');
  if (!apiKey || !secretKey || !passphrase) throw new Error('Missing api_key/secret_key/passphrase in profile');
  return { apiKey, secretKey, passphrase, baseUrl };
}

function isoNow() { return new Date().toISOString(); }

function sign(secretKey, method, requestPath, query = '') {
  const ts = isoNow();
  const prehash = ts + method.toUpperCase() + requestPath + (query ? `?${query}` : '');
  const sig = crypto.createHmac('sha256', secretKey).update(prehash).digest('base64');
  return { ts, sig };
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function okxGet(client, requestPath, params = {}) {
  const url = new URL(client.baseUrl + requestPath);
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    url.searchParams.set(k, String(v));
  }
  const query = url.searchParams.toString();

  for (let attempt = 0; attempt < 8; attempt++) {
    const { ts, sig } = sign(client.secretKey, 'GET', requestPath, query);
    const res = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'OK-ACCESS-KEY': client.apiKey,
        'OK-ACCESS-SIGN': sig,
        'OK-ACCESS-TIMESTAMP': ts,
        'OK-ACCESS-PASSPHRASE': client.passphrase,
        'Content-Type': 'application/json'
      }
    });
    const text = await res.text();

    if (res.status === 429) {
      await sleep(Math.min(60000, 800 * (2 ** attempt)));
      continue;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 500)}`);

    let json;
    try { json = JSON.parse(text); } catch { throw new Error(`Bad JSON: ${text.slice(0, 200)}`); }
    if (json.code === '50011' || json.code === '50013') {
      await sleep(Math.min(60000, 800 * (2 ** attempt)));
      continue;
    }
    if (json.code !== '0') throw new Error(`OKX code=${json.code} msg=${json.msg}`);

    await sleep(120);
    return json.data;
  }
  throw new Error('Too many retries');
}

function jsonl(filePath) {
  const s = fs.createWriteStream(filePath, { flags: 'a' });
  return {
    write: (obj) => s.write(JSON.stringify(obj) + '\n'),
    end: () => s.end()
  };
}

function rangeChunksMs(daysBack, chunkDays = 7) {
  const end = Date.now();
  const start = end - daysBack * 24 * 3600 * 1000;
  const chunks = [];
  let cur = start;
  const step = chunkDays * 24 * 3600 * 1000;
  while (cur < end) {
    const next = Math.min(end, cur + step);
    chunks.push([cur, next]);
    cur = next;
  }
  return chunks;
}

async function exportBillsArchive(client, instType, outPath) {
  const w = jsonl(outPath);
  let after;
  let total = 0;
  for (let i = 0; i < 500; i++) {
    const data = await okxGet(client, '/api/v5/account/bills-archive', { instType, limit: 100, after });
    if (!Array.isArray(data) || data.length === 0) break;
    for (const row of data) w.write(row);
    total += data.length;
    const lastId = data[data.length - 1]?.billId;
    if (!lastId || String(lastId) === String(after)) break;
    after = String(lastId);
  }
  w.end();
  return total;
}

async function exportOrdersByTime(client, instType, instId, outPath, daysBack) {
  const w = jsonl(outPath);
  let total = 0;
  for (const [begin, end] of rangeChunksMs(daysBack, 7)) {
    const data = await okxGet(client, '/api/v5/trade/orders-history-archive', { instType, instId, begin, end, limit: 100 });
    for (const row of data) { w.write(row); total++; }
  }
  w.end();
  return total;
}

async function exportFillsByTime(client, instType, instId, outPath, daysBack) {
  const w = jsonl(outPath);
  let total = 0;
  for (const [begin, end] of rangeChunksMs(daysBack, 7)) {
    const data = await okxGet(client, '/api/v5/trade/fills-history', { instType, instId, begin, end, limit: 100 });
    for (const row of data) { w.write(row); total++; }
  }
  w.end();
  return total;
}

async function main() {
  const args = parseArgs();
  const client = loadProfile(args.profile);
  fs.mkdirSync(args.outDir, { recursive: true });

  const swapBillsN = await exportBillsArchive(client, 'SWAP', path.join(args.outDir, 'bills_SWAP_archive.jsonl'));
  const futBillsN = await exportBillsArchive(client, 'FUTURES', path.join(args.outDir, 'bills_FUTURES_archive.jsonl'));

  // discover instIds from swap bills
  const swapPath = path.join(args.outDir, 'bills_SWAP_archive.jsonl');
  const instSet = new Set();
  if (fs.existsSync(swapPath)) {
    const lines = fs.readFileSync(swapPath, 'utf8').split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      try { const o = JSON.parse(line); if (o?.instId) instSet.add(o.instId); } catch {}
    }
  }
  const instIds = Array.from(instSet).sort();
  fs.writeFileSync(path.join(args.outDir, 'swap_instIds.txt'), instIds.join('\n'));

  const totals = [];
  for (const instId of instIds) {
    const safe = instId.replace(/[^A-Za-z0-9\-]/g, '_');
    const fillsN = await exportFillsByTime(client, 'SWAP', instId, path.join(args.outDir, `fills_SWAP_${safe}.jsonl`), args.days);
    const ordN = await exportOrdersByTime(client, 'SWAP', instId, path.join(args.outDir, `orders_SWAP_${safe}.jsonl`), args.days);
    totals.push({ instId, fillsN, ordN });
  }

  const summary = { profile: args.profile, days: args.days, swapBillsN, futBillsN, instIdCount: instIds.length, totals };
  fs.writeFileSync(path.join(args.outDir, 'SUMMARY.json'), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary));
}

main().catch((e) => {
  console.error(e?.stack || String(e));
  process.exit(1);
});
