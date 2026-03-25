// Export OKX CEX trade history (SWAP/FUTURES/SPOT/Savings) into JSONL.
// Reads credentials from ~/.okx/config.toml (Agent Trade Kit profile format).

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
    if (mKV && cur) { profiles[cur][mKV[1]] = mKV[2].trim(); }
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
    if (res.status === 429) { await sleep(Math.min(60000, 800 * (2 ** attempt))); continue; }
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 500)}`);
    let json;
    try { json = JSON.parse(text); } catch { throw new Error(`Bad JSON: ${text.slice(0, 200)}`); }
    if (json.code === '50011' || json.code === '50013') { await sleep(Math.min(60000, 800 * (2 ** attempt))); continue; }
    if (json.code !== '0') throw new Error(`OKX code=${json.code} msg=${json.msg}`);
    await sleep(120);
    return json.data;
  }
  throw new Error('Too many retries');
}

async function okxGetSafe(client, requestPath, params = {}) {
  try {
    return await okxGet(client, requestPath, params);
  } catch (e) {
    console.error(`[WARN] ${requestPath} failed (skipping): ${e.message}`);
    return [];
  }
}

function jsonl(filePath) {
  const s = fs.createWriteStream(filePath, { flags: 'a' });
  return { write: (obj) => s.write(JSON.stringify(obj) + '\n'), end: () => s.end() };
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

function discoverInstIds(billsPath) {
  const instSet = new Set();
  if (!fs.existsSync(billsPath)) return [];
  const lines = fs.readFileSync(billsPath, 'utf8').split(/\r?\n/).filter(Boolean);
  for (const line of lines) {
    try { const o = JSON.parse(line); if (o?.instId) instSet.add(o.instId); } catch {}
  }
  return Array.from(instSet).sort();
}

async function exportSavingsHistory(client, outPath) {
  const w = jsonl(outPath);
  let total = 0;
  let after;
  for (let i = 0; i < 50; i++) {
    const params = { limit: 100 };
    if (after) params.after = after;
    const data = await okxGetSafe(client, '/api/v5/finance/savings/purchase-redempt-history', params);
    if (!Array.isArray(data) || data.length === 0) break;
    for (const row of data) { w.write(row); total++; }
    if (data.length < 100) break;
    const last = data[data.length - 1];
    const lastTs = last?.startTime || last?.ts;
    if (!lastTs || String(lastTs) === String(after)) break;
    after = String(lastTs);
  }
  w.end();
  return total;
}

async function exportSavingsBalance(client, outPath) {
  const data = await okxGetSafe(client, '/api/v5/finance/savings/balance', {});
  const w = jsonl(outPath);
  let total = 0;
  if (Array.isArray(data)) { for (const row of data) { w.write(row); total++; } }
  w.end();
  return total;
}

async function exportEarnOrdersHistory(client, outPath, daysBack) {
  const w = jsonl(outPath);
  let total = 0;
  let after;
  for (let i = 0; i < 50; i++) {
    const params = { limit: 100 };
    if (after) params.after = after;
    const data = await okxGetSafe(client, '/api/v5/finance/staking-defi/orders-history', params);
    if (!Array.isArray(data) || data.length === 0) break;
    for (const row of data) { w.write(row); total++; }
    if (data.length < 100) break;
    const last = data[data.length - 1];
    const lastId = last?.ordId || last?.id;
    if (!lastId || String(lastId) === String(after)) break;
    after = String(lastId);
  }
  w.end();
  return total;
}

async function main() {
  const args = parseArgs();
  const client = loadProfile(args.profile);
  fs.mkdirSync(args.outDir, { recursive: true });

  console.error('[INFO] Exporting SWAP bills...');
  const swapBillsN = await exportBillsArchive(client, 'SWAP', path.join(args.outDir, 'bills_SWAP_archive.jsonl'));
  const swapInstIds = discoverInstIds(path.join(args.outDir, 'bills_SWAP_archive.jsonl'));
  fs.writeFileSync(path.join(args.outDir, 'swap_instIds.txt'), swapInstIds.join('\n'));
  const swapTotals = [];
  for (const instId of swapInstIds) {
    console.error(`[INFO] Exporting SWAP fills/orders: ${instId}`);
    const safe = instId.replace(/[^A-Za-z0-9\-]/g, '_');
    const fillsN = await exportFillsByTime(client, 'SWAP', instId, path.join(args.outDir, `fills_SWAP_${safe}.jsonl`), args.days);
    const ordN = await exportOrdersByTime(client, 'SWAP', instId, path.join(args.outDir, `orders_SWAP_${safe}.jsonl`), args.days);
    swapTotals.push({ instId, fillsN, ordN });
  }

  console.error('[INFO] Exporting FUTURES bills...');
  const futBillsN = await exportBillsArchive(client, 'FUTURES', path.join(args.outDir, 'bills_FUTURES_archive.jsonl'));

  console.error('[INFO] Exporting SPOT bills...');
  const spotBillsN = await exportBillsArchive(client, 'SPOT', path.join(args.outDir, 'bills_SPOT_archive.jsonl'));
  const spotInstIds = discoverInstIds(path.join(args.outDir, 'bills_SPOT_archive.jsonl'));
  fs.writeFileSync(path.join(args.outDir, 'spot_instIds.txt'), spotInstIds.join('\n'));
  const spotTotals = [];
  for (const instId of spotInstIds) {
    console.error(`[INFO] Exporting SPOT fills/orders: ${instId}`);
    const safe = instId.replace(/[^A-Za-z0-9\-]/g, '_');
    const fillsN = await exportFillsByTime(client, 'SPOT', instId, path.join(args.outDir, `fills_SPOT_${safe}.jsonl`), args.days);
    const ordN = await exportOrdersByTime(client, 'SPOT', instId, path.join(args.outDir, `orders_SPOT_${safe}.jsonl`), args.days);
    spotTotals.push({ instId, fillsN, ordN });
  }

  console.error('[INFO] Exporting MARGIN bills...');
  const marginBillsN = await exportBillsArchive(client, 'MARGIN', path.join(args.outDir, 'bills_MARGIN_archive.jsonl'));

  console.error('[INFO] Exporting Savings history...');
  const savingsHistN = await exportSavingsHistory(client, path.join(args.outDir, 'savings_history.jsonl'));
  const savingsBalN = await exportSavingsBalance(client, path.join(args.outDir, 'savings_balance.jsonl'));
  const earnHistN = await exportEarnOrdersHistory(client, path.join(args.outDir, 'earn_orders_history.jsonl'), args.days);

  const summary = {
    profile: args.profile, days: args.days,
    swap: { billsN: swapBillsN, instIdCount: swapInstIds.length, totals: swapTotals },
    futures: { billsN: futBillsN },
    spot: { billsN: spotBillsN, instIdCount: spotInstIds.length, totals: spotTotals },
    margin: { billsN: marginBillsN },
    savings: { historyN: savingsHistN, balanceN: savingsBalN },
    earn: { historyN: earnHistN },
  };
  fs.writeFileSync(path.join(args.outDir, 'SUMMARY.json'), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary));
}

main().catch((e) => { console.error(e?.stack || String(e)); process.exit(1); });
