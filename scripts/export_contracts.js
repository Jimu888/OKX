// Export OKX CEX contract history (SWAP/FUTURES) into JSONL.
// Data fetching goes through the official OKX Agent Trade Kit MCP server.
// The downstream analysis keeps the same raw filenames and JSONL layout.

import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const MCP_REQUEST_TIMEOUT_MS = 15000;

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
  if (!Number.isFinite(out.days) || out.days <= 0) throw new Error('Missing or invalid --days');
  return out;
}

function jsonl(filePath) {
  const s = fs.createWriteStream(filePath, { flags: 'a' });
  return {
    write: (obj) => s.write(JSON.stringify(obj) + '\n'),
    end: () => s.end(),
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

function toMs(row, keys) {
  for (const key of keys) {
    const raw = row?.[key];
    if (raw === undefined || raw === null || raw === '') continue;
    const ms = Number(raw);
    if (Number.isFinite(ms)) return ms;
  }
  return NaN;
}

function normalizeResult(result) {
  if (Array.isArray(result)) return result;
  if (result && typeof result === 'object') {
    if (Array.isArray(result.data)) return result.data;
    if (result.structuredContent && Array.isArray(result.structuredContent.data)) return result.structuredContent.data;
  }
  return [];
}

function pickCursor(row, candidates) {
  for (const key of candidates) {
    const value = row?.[key];
    if (value !== undefined && value !== null && String(value).length > 0) {
      return String(value);
    }
  }
  return '';
}

class McpClient {
  constructor(command, args) {
    this.command = command;
    this.args = args;
    this.proc = null;
    this.buffer = Buffer.alloc(0);
    this.nextId = 1;
    this.pending = new Map();
    this.ready = false;
    this.initPromise = null;
  }

  async start() {
    if (this.proc) return;
    this.proc = spawn(this.command, this.args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: process.env,
    });

    await new Promise((resolve, reject) => {
      const onSpawn = () => {
        this.proc?.off('error', onError);
        resolve();
      };
      const onError = (err) => {
        this.proc?.off('spawn', onSpawn);
        reject(err);
      };
      this.proc.once('spawn', onSpawn);
      this.proc.once('error', onError);
    });

    this.proc.stdout.on('data', (chunk) => this.onStdout(chunk));
    this.proc.stderr.on('data', (chunk) => {
      const text = chunk.toString('utf8').trim();
      if (text) process.stderr.write(`[okx-mcp] ${text}\n`);
    });
    this.proc.on('exit', (code, signal) => {
      const err = new Error(`MCP process exited unexpectedly (${signal ?? code ?? 'unknown'})`);
      for (const { reject } of this.pending.values()) {
        reject(err);
      }
      this.pending.clear();
      this.proc = null;
    });
    this.proc.on('error', (err) => {
      for (const { reject } of this.pending.values()) {
        reject(err);
      }
      this.pending.clear();
    });

    await this.request('initialize', {
      protocolVersion: '2024-11-05',
      clientInfo: { name: 'okx-trade-history-analyzer', version: '1.0.0' },
      capabilities: {},
    });
    this.notify('notifications/initialized', {});
    this.ready = true;
  }

  stop() {
    if (this.proc) {
      this.proc.kill();
      this.proc = null;
    }
  }

  notify(method, params) {
    this.sendRaw({ jsonrpc: '2.0', method, params });
  }

  request(method, params) {
    return new Promise((resolve, reject) => {
      const id = this.nextId++;
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`MCP request timed out: ${method}`));
      }, MCP_REQUEST_TIMEOUT_MS);
      this.pending.set(id, {
        resolve: (value) => {
          clearTimeout(timeout);
          resolve(value);
        },
        reject: (err) => {
          clearTimeout(timeout);
          reject(err);
        },
      });
      this.sendRaw({ jsonrpc: '2.0', id, method, params });
    });
  }

  sendRaw(payload) {
    if (!this.proc?.stdin) throw new Error('MCP process is not running');
    const body = Buffer.from(JSON.stringify(payload), 'utf8');
    const header = Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, 'utf8');
    this.proc.stdin.write(Buffer.concat([header, body]));
  }

  onStdout(chunk) {
    this.buffer = Buffer.concat([this.buffer, chunk]);

    while (true) {
      const contentIdx = this.findHeaderStart();
      if (contentIdx === -1) {
        if (this.buffer.length > 64 * 1024) {
          this.buffer = this.buffer.subarray(this.buffer.length - 8 * 1024);
        }
        return;
      }
      if (contentIdx > 0) {
        this.buffer = this.buffer.subarray(contentIdx);
      }

      const headerEnd = this.findHeaderEnd();
      if (headerEnd === -1) return;

      const headerText = this.buffer.slice(0, headerEnd).toString('utf8');
      const headers = {};
      for (const line of headerText.split(/\r?\n/)) {
        const idx = line.indexOf(':');
        if (idx === -1) continue;
        headers[line.slice(0, idx).trim().toLowerCase()] = line.slice(idx + 1).trim();
      }

      const len = Number(headers['content-length']);
      if (!Number.isFinite(len) || len < 0) {
        throw new Error(`Invalid MCP message headers: ${headerText}`);
      }

      const separatorLen = this.buffer[headerEnd] === 13 ? 4 : 2;
      const totalLen = headerEnd + separatorLen + len;
      if (this.buffer.length < totalLen) return;

      const body = this.buffer.slice(headerEnd + separatorLen, totalLen).toString('utf8');
      this.buffer = this.buffer.slice(totalLen);

      let msg;
      try {
        msg = JSON.parse(body);
      } catch (err) {
        throw new Error(`Failed to parse MCP message: ${body.slice(0, 200)}`);
      }

      this.handleMessage(msg);
    }
  }

  findHeaderStart() {
    const exact = this.buffer.indexOf('Content-Length:');
    if (exact !== -1) return exact;

    const lower = this.buffer.toString('utf8').toLowerCase();
    return lower.indexOf('content-length:');
  }

  findHeaderEnd() {
    const crlf = this.buffer.indexOf('\r\n\r\n');
    if (crlf !== -1) return crlf;
    return this.buffer.indexOf('\n\n');
  }

  handleMessage(msg) {
    if (!msg || typeof msg !== 'object') return;

    if (Object.prototype.hasOwnProperty.call(msg, 'id')) {
      const pending = this.pending.get(msg.id);
      if (!pending) return;
      this.pending.delete(msg.id);
      if (msg.error) {
        pending.reject(new Error(msg.error.message || 'MCP request failed'));
        return;
      }
      pending.resolve(msg.result);
    }
  }

  async callTool(name, args) {
    if (!this.ready) {
      throw new Error('MCP client is not initialized');
    }
    const result = await this.request('tools/call', { name, arguments: args });
    if (result?.isError) {
      const text = Array.isArray(result.content) ? result.content.map((c) => c?.text ?? '').join('\n') : '';
      throw new Error(text || `Tool call failed: ${name}`);
    }
    const structured = result?.structuredContent;
    if (structured && typeof structured === 'object' && Array.isArray(structured.data)) return structured.data;
    const firstText = Array.isArray(result?.content) ? result.content.find((c) => c?.type === 'text')?.text : '';
    if (!firstText) return [];
    const parsed = JSON.parse(firstText);
    if (parsed && typeof parsed === 'object' && Array.isArray(parsed.data)) return parsed.data;
    return [];
  }
}

function splitArgString(value) {
  if (!value) return [];
  return value.match(/"[^"]*"|'[^']*'|\S+/g)?.map((part) => part.replace(/^["']|["']$/g, '')) ?? [];
}

function spawnAndCollect(command, args) {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, { env: process.env });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (chunk) => {
      stdout += chunk.toString('utf8');
    });
    proc.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
    });
    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || stdout.trim() || `Command failed: ${command}`));
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

function buildCliLauncher(profile) {
  const custom = process.env.OKX_CLI_CMD?.trim();
  if (custom) {
    return {
      command: custom,
      baseArgs: splitArgString(process.env.OKX_CLI_ARGS),
    };
  }

  if (process.platform === 'win32') {
    return {
      command: 'cmd',
      baseArgs: ['/c', 'npx', '-y', '@okx_ai/okx-trade-cli', '--profile', profile],
    };
  }

  return {
    command: 'npx',
    baseArgs: ['-y', '@okx_ai/okx-trade-cli', '--profile', profile],
  };
}

async function runCliJson(profile, subArgs) {
  const launcher = buildCliLauncher(profile);
  const result = await spawnAndCollect(launcher.command, [...launcher.baseArgs, ...subArgs, '--json']);
  return JSON.parse(result.stdout || '[]');
}

async function withMcpClient(profile, fn) {
  const custom = process.env.OKX_MCP_CMD?.trim();
  const command = custom || (process.platform === 'win32' ? 'cmd' : 'npx');
  const args = custom
    ? []
    : process.platform === 'win32'
      ? ['/c', 'npx', '-y', '@okx_ai/okx-trade-mcp', '--profile', profile, '--modules', 'account,swap', '--read-only', '--no-log']
      : ['-y', '@okx_ai/okx-trade-mcp', '--profile', profile, '--modules', 'account,swap', '--read-only', '--no-log'];
  const client = new McpClient(command, args);
  try {
    await client.start();
    return await fn(client);
  } finally {
    client.stop();
  }
}

async function exportViaCli(profile, args) {
  fs.mkdirSync(args.outDir, { recursive: true });

  const swapBills = await runCliJson(profile, ['account', 'bills', '--archive', '--instType', 'SWAP']);
  const futuresBills = await runCliJson(profile, ['account', 'bills', '--archive', '--instType', 'FUTURES']);
  fs.writeFileSync(path.join(args.outDir, 'bills_SWAP_archive.jsonl'), swapBills.map((row) => JSON.stringify(row)).join('\n') + (swapBills.length ? '\n' : ''));
  fs.writeFileSync(path.join(args.outDir, 'bills_FUTURES_archive.jsonl'), futuresBills.map((row) => JSON.stringify(row)).join('\n') + (futuresBills.length ? '\n' : ''));

  const instSet = new Set();
  for (const row of swapBills) {
    if (row?.instId) instSet.add(row.instId);
  }
  const instIds = Array.from(instSet).sort();
  fs.writeFileSync(path.join(args.outDir, 'swap_instIds.txt'), instIds.join('\n'));

  const totals = [];
  for (const instId of instIds) {
    const safe = instId.replace(/[^A-Za-z0-9\-]/g, '_');
    const fills = await runCliJson(profile, ['swap', 'fills', '--instId', instId, '--archive']);
    fs.writeFileSync(path.join(args.outDir, `fills_SWAP_${safe}.jsonl`), fills.map((row) => JSON.stringify(row)).join('\n') + (fills.length ? '\n' : ''));

    const orders = await runCliJson(profile, ['swap', 'orders', '--instId', instId, '--history']);
    fs.writeFileSync(path.join(args.outDir, `orders_SWAP_${safe}.jsonl`), orders.map((row) => JSON.stringify(row)).join('\n') + (orders.length ? '\n' : ''));
    totals.push({ instId, fillsN: fills.length, ordN: orders.length, transport: 'cli-fallback' });
  }

  const summary = {
    profile,
    days: args.days,
    swapBillsN: swapBills.length,
    futBillsN: futuresBills.length,
    instIdCount: instIds.length,
    totals,
    transport: 'cli-fallback',
  };
  fs.writeFileSync(path.join(args.outDir, 'SUMMARY.json'), JSON.stringify(summary, null, 2));
  return summary;
}

async function exportBillsArchive(client, instType, outPath) {
  const w = jsonl(outPath);
  let after;
  let total = 0;
  for (let i = 0; i < 500; i++) {
    const data = normalizeResult(await client.callTool('account_get_bills_archive', {
      instType,
      limit: 100,
      after,
    }));
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

async function fetchWindowPaged(client, toolName, args, cursorKeys) {
  const rows = [];
  let after;
  for (let i = 0; i < 100; i++) {
    const page = normalizeResult(await client.callTool(toolName, { ...args, after, limit: 100 }));
    if (!Array.isArray(page) || page.length === 0) break;
    rows.push(...page);
    const cursor = pickCursor(page[page.length - 1], cursorKeys);
    if (!cursor || cursor === after) break;
    after = cursor;
    if (page.length < 100) break;
  }
  return rows;
}

async function exportOrdersByTime(client, instType, instId, outPath, daysBack) {
  const w = jsonl(outPath);
  let total = 0;
  for (const [begin, end] of rangeChunksMs(daysBack, 7)) {
    const data = await fetchWindowPaged(client, 'swap_get_orders', {
      instType,
      status: 'archive',
      instId,
      begin,
      end,
    }, ['ordId', 'clOrdId', 'billId']);
    for (const row of data) {
      w.write(row);
      total++;
    }
  }
  w.end();
  return total;
}

async function exportFillsByTime(client, instType, instId, outPath, daysBack) {
  const w = jsonl(outPath);
  let total = 0;

  for (const [begin, end] of rangeChunksMs(daysBack, 7)) {
    const data = await fetchWindowPaged(client, 'swap_get_fills', {
      instType,
      archive: true,
      instId,
      begin,
      end,
    }, ['tradeId', 'fillId', 'ordId']);
    for (const row of data) {
      w.write(row);
      total++;
    }
  }
  w.end();

  return total;
}

async function main() {
  const args = parseArgs();
  fs.mkdirSync(args.outDir, { recursive: true });
  let summary;
  try {
    summary = await withMcpClient(args.profile, async (client) => {
      const swapBillsN = await exportBillsArchive(client, 'SWAP', path.join(args.outDir, 'bills_SWAP_archive.jsonl'));
      const futBillsN = await exportBillsArchive(client, 'FUTURES', path.join(args.outDir, 'bills_FUTURES_archive.jsonl'));

      const swapPath = path.join(args.outDir, 'bills_SWAP_archive.jsonl');
      const instSet = new Set();
      if (fs.existsSync(swapPath)) {
        const lines = fs.readFileSync(swapPath, 'utf8').split(/\r?\n/).filter(Boolean);
        for (const line of lines) {
          try {
            const o = JSON.parse(line);
            if (o?.instId) instSet.add(o.instId);
          } catch {
            // ignore malformed line
          }
        }
      }
      const instIds = Array.from(instSet).sort();
      fs.writeFileSync(path.join(args.outDir, 'swap_instIds.txt'), instIds.join('\n'));

      const totals = [];
      for (const instId of instIds) {
        const safe = instId.replace(/[^A-Za-z0-9\-]/g, '_');
        const fillsN = await exportFillsByTime(
          client,
          'SWAP',
          instId,
          path.join(args.outDir, `fills_SWAP_${safe}.jsonl`),
          args.days,
        );
        const ordN = await exportOrdersByTime(
          client,
          'SWAP',
          instId,
          path.join(args.outDir, `orders_SWAP_${safe}.jsonl`),
          args.days,
        );
        totals.push({ instId, fillsN, ordN, transport: 'mcp' });
      }

      const summary = {
        profile: args.profile,
        days: args.days,
        swapBillsN,
        futBillsN,
        instIdCount: instIds.length,
        totals,
        transport: 'mcp',
      };
      fs.writeFileSync(path.join(args.outDir, 'SUMMARY.json'), JSON.stringify(summary, null, 2));
      return summary;
    });
  } catch (err) {
    process.stderr.write(`[okx-export] MCP transport failed, falling back to official CLI: ${err?.message ?? err}\n`);
    summary = await exportViaCli(args.profile, args);
  }

  console.log(JSON.stringify(summary));
}

main().catch((e) => {
  console.error(e?.stack || String(e));
  process.exit(1);
});
