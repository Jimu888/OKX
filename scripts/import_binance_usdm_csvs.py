import argparse, csv, json, os, re
from datetime import datetime, timezone

UTC = timezone.utc


def parse_utc(s: str):
    # formats seen: 2026-02-02 08:48:42
    s = (s or '').strip().strip('"')
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    return None


def dt_to_ms(dt):
    return int(dt.timestamp() * 1000)


def parse_num(s: str):
    s = (s or '').strip().strip('"')
    if s in ('', '0E-8', '0E-7', '0E-6'):
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_fee_cell(cell: str):
    # e.g. "11.46034050 USDT" or "0.00027446 BNB"
    cell = (cell or '').strip().strip('"')
    if not cell:
        return 0.0, None
    m = re.match(r"^([+-]?[0-9]*\.?[0-9]+)\s+([A-Za-z0-9]+)$", cell)
    if not m:
        return 0.0, None
    return float(m.group(1)), m.group(2)


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--orders', required=True)
    ap.add_argument('--trades', required=True)
    ap.add_argument('--income', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    out = args.out
    os.makedirs(out, exist_ok=True)

    # 1) trades -> fills_SWAP_*.jsonl
    fills_by_sym = {}
    with open(args.trades, 'r', encoding='utf-8-sig', newline='') as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            t = parse_utc(row.get('Time(UTC)'))
            if not t:
                continue
            sym = (row.get('Symbol') or 'UNKNOWN').strip().strip('"')
            realized = parse_num(row.get('Realized Profit'))
            fee_val, fee_asset = parse_fee_cell(row.get('Fee'))

            # Only keep USDT-denominated fee as fee; otherwise store separately (no FX conversion).
            fee_usdt = -fee_val if (fee_asset == 'USDT' and fee_val != 0) else 0.0
            fee_other = -fee_val if (fee_asset and fee_asset != 'USDT' and fee_val != 0) else 0.0

            r = {
                'fillTime': dt_to_ms(t),
                'instId': sym,
                'fillPnl': realized,
                'fee': fee_usdt,
                'feeAsset': fee_asset,
                'feeOther': fee_other,
                'feeOtherAsset': fee_asset if fee_asset != 'USDT' else None,
                'raw': row,
            }
            fills_by_sym.setdefault(sym, []).append(r)

    for sym, rows in fills_by_sym.items():
        rows.sort(key=lambda x: x['fillTime'])
        write_jsonl(os.path.join(out, f"fills_SWAP_{sym}.jsonl"), rows)

    # 2) orders -> orders_SWAP_*.jsonl (pnl/fee unavailable here; set 0; keep metadata)
    orders_by_sym = {}
    with open(args.orders, 'r', encoding='utf-8-sig', newline='') as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            t = parse_utc(row.get('Time(UTC)'))
            if not t:
                continue
            sym = (row.get('Symbol') or 'UNKNOWN').strip().strip('"')
            r = {
                'cTime': dt_to_ms(t),
                'uTime': dt_to_ms(parse_utc(row.get('Update Time')) or t),
                'instId': sym,
                'pnl': 0.0,
                'fee': 0.0,
                'state': (row.get('Status') or '').strip().strip('"'),
                'ordType': (row.get('Type') or '').strip().strip('"'),
                'side': (row.get('Side') or '').strip().strip('"'),
                'posSide': (row.get('Position Side') or '').strip().strip('"'),
                'raw': row,
            }
            orders_by_sym.setdefault(sym, []).append(r)

    for sym, rows in orders_by_sym.items():
        rows.sort(key=lambda x: x['cTime'])
        write_jsonl(os.path.join(out, f"orders_SWAP_{sym}.jsonl"), rows)

    # 3) income -> bills_SWAP_archive.jsonl
    bills = []
    with open(args.income, 'r', encoding='utf-8-sig', newline='') as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            t = parse_utc(row.get('Date(UTC)'))
            if not t:
                continue
            sym = (row.get('Symbol') or 'UNKNOWN').strip().strip('"')
            ty = (row.get('type') or '').strip().strip('"')
            amt = parse_num(row.get('Amount'))
            asset = (row.get('Asset') or '').strip().strip('"')

            # Income export is already the account ledger for futures.
            # We treat USDT Amount as pnl-like cashflow; other assets are recorded but not converted.
            pnl = amt if asset == 'USDT' else 0.0
            fee = 0.0

            bills.append({
                'ts': dt_to_ms(t),
                'instId': sym,
                'type': ty,
                'pnl': pnl,
                'fee': fee,
                'asset': asset,
                'amount': amt,
                'raw': row,
            })

    bills.sort(key=lambda x: x['ts'])
    write_jsonl(os.path.join(out, 'bills_SWAP_archive.jsonl'), bills)

    # coverage hint
    meta = {
        'source': 'binance_usdm_export',
        'exchange': 'binance',
        'market': 'USDⓈ-M Futures',
        'orders_csv': args.orders,
        'trades_csv': args.trades,
        'income_csv': args.income,
        'notes': [
            'Trade fee in non-USDT (e.g., BNB) is recorded in feeOther/feeOtherAsset but not FX-converted.',
            'Order-level pnl/fee are set to 0 (Binance order export does not include realized pnl).',
            'Income Amount is counted as pnl only when Asset==USDT; other assets are not FX-converted.'
        ]
    }
    with open(os.path.join(out, 'IMPORT_META.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
