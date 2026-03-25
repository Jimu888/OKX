import argparse, json, os, math
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))
WD = ['周一','周二','周三','周四','周五','周六','周日']


def ms_to_dt(ms):
    try:
        ms = int(ms)
    except Exception:
        return None
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc)


def read_jsonl(fp):
    out=[]
    if not os.path.exists(fp):
        return out
    with open(fp,'r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def equity_metrics(net_series):
    if not net_series:
        return dict(max_drawdown=0.0, max_consecutive_win=0, max_consecutive_loss=0)
    cum=[]
    c=0.0
    for x in net_series:
        c += x
        cum.append(c)
    peak=-1e18
    mdd=0.0
    for v in cum:
        if v>peak:
            peak=v
        dd=peak-v
        if dd>mdd:
            mdd=dd
    best_win=best_loss=cur_win=cur_loss=0
    for x in net_series:
        if x>0:
            cur_win += 1
            cur_loss = 0
        elif x<0:
            cur_loss += 1
            cur_win = 0
        else:
            cur_win = 0
            cur_loss = 0
        best_win=max(best_win,cur_win)
        best_loss=max(best_loss,cur_loss)
    return dict(max_drawdown=mdd, max_consecutive_win=best_win, max_consecutive_loss=best_loss)


def summarize_pnl(pnls):
    pnls=[float(x) for x in pnls]
    wins=[x for x in pnls if x>0]
    losses=[x for x in pnls if x<0]
    win_rate=len(wins)/len(pnls) if pnls else 0.0
    avg_win=sum(wins)/len(wins) if wins else 0.0
    avg_loss=sum(losses)/len(losses) if losses else 0.0
    profit_factor=(sum(wins)/abs(sum(losses))) if losses else float('inf')
    rr=(avg_win/abs(avg_loss)) if avg_loss!=0 else float('inf')
    return dict(win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss, profit_factor=profit_factor, rr=rr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    raw = args.raw
    out = args.out
    os.makedirs(out, exist_ok=True)

    bills = read_jsonl(os.path.join(raw, 'bills_SWAP_archive.jsonl'))

    fills=[]
    orders=[]
    for fn in os.listdir(raw):
        if fn.startswith('fills_SWAP_') and fn.endswith('.jsonl'):
            fills += read_jsonl(os.path.join(raw, fn))
        if fn.startswith('orders_SWAP_') and fn.endswith('.jsonl'):
            orders += read_jsonl(os.path.join(raw, fn))

    bill_times=[ms_to_dt(r.get('ts') or r.get('fillTime') or r.get('uTime')) for r in bills]
    bill_times=[t for t in bill_times if t]
    fill_rows=[]
    for r in fills:
        t=ms_to_dt(r.get('fillTime') or r.get('ts'))
        if not t: continue
        pnl=float(r.get('fillPnl') or 0)
        fee=float(r.get('fee') or 0)
        fill_rows.append((t, r.get('instId') or 'UNKNOWN', pnl, fee))
    fill_rows.sort(key=lambda x: x[0])

    order_rows=[]
    for o in orders:
        t=ms_to_dt(o.get('cTime') or o.get('uTime') or o.get('fillTime'))
        if not t: continue
        p=float(o.get('pnl') or 0)
        f=float(o.get('fee') or 0)
        order_rows.append((t, o.get('instId') or 'UNKNOWN', p, f, o))
    order_rows.sort(key=lambda x: x[0])

    inst_ids=sorted({r.get('instId') for r in bills if r.get('instId')})

    # bills summary
    bills_pnl=[float(r.get('pnl') or 0) for r in bills]
    bills_fee=[float(r.get('fee') or 0) for r in bills]
    bills_net=[p+f for p,f in zip(bills_pnl, bills_fee)]

    funding=0.0
    by_bill_type=defaultdict(lambda:{'net':0.0,'n':0})
    by_symbol_bill=defaultdict(lambda:{'net':0.0,'pnl':0.0,'fee':0.0,'n':0})
    for r in bills:
        ty=str(r.get('type') or '')
        p=float(r.get('pnl') or 0)
        f=float(r.get('fee') or 0)
        n=p+f
        by_bill_type[ty]['net'] += n
        by_bill_type[ty]['n'] += 1
        if ty=='8':
            funding += n
        sym=r.get('instId') or 'UNKNOWN'
        by_symbol_bill[sym]['net'] += n
        by_symbol_bill[sym]['pnl'] += p
        by_symbol_bill[sym]['fee'] += f
        by_symbol_bill[sym]['n'] += 1

    bills_summary={
        'rows': len(bills),
        'start_utc': min(bill_times).isoformat() if bill_times else None,
        'end_utc': max(bill_times).isoformat() if bill_times else None,
        'pnl_total': sum(bills_pnl),
        'fee_total': sum(bills_fee),
        'net_total': sum(bills_net),
        'funding_est': funding,
        'by_type': dict(by_bill_type)
    }

    # fills behavior summary
    fill_net=[p+f for _,_,p,f in fill_rows]
    active_days=sorted({(t.astimezone(CN_TZ).date()) for t,_,_,_ in fill_rows})
    by_hour=defaultdict(lambda:{'net':0.0,'n':0})
    by_wday=defaultdict(lambda:{'net':0.0,'n':0})
    for t,_,p,f in fill_rows:
        cn=t.astimezone(CN_TZ)
        by_hour[cn.hour]['net'] += p+f
        by_hour[cn.hour]['n'] += 1
        by_wday[cn.weekday()]['net'] += p+f
        by_wday[cn.weekday()]['n'] += 1

    fills_summary={
        'rows': len(fill_rows),
        'start_utc': fill_rows[0][0].isoformat() if fill_rows else None,
        'end_utc': fill_rows[-1][0].isoformat() if fill_rows else None,
        'net': sum(fill_net),
        'active_days': len(active_days),
        'trades_per_active_day': (len(fill_rows)/len(active_days)) if active_days else 0.0,
        'by_hour_cn': dict(by_hour),
        'by_wday_cn': dict(by_wday),
        'quality_fill': summarize_pnl(fill_net),
        'equity_fill': equity_metrics(fill_net),
    }

    # orders summary
    ord_net=[p+f for _,_,p,f,_ in order_rows]
    state=Counter([o.get('state') for _,_,_,_,o in order_rows])
    ordType=Counter([o.get('ordType') for _,_,_,_,o in order_rows])
    side=Counter([o.get('side') for _,_,_,_,o in order_rows])
    posSide=Counter([o.get('posSide') for _,_,_,_,o in order_rows])

    orders_summary={
        'rows': len(order_rows),
        'start_utc': order_rows[0][0].isoformat() if order_rows else None,
        'end_utc': order_rows[-1][0].isoformat() if order_rows else None,
        'pnl_total': sum([p for _,_,p,_,_ in order_rows]),
        'fee_total': sum([f for _,_,_,f,_ in order_rows]),
        'net_total': sum(ord_net),
        'state': dict(state),
        'ordType': dict(ordType),
        'side': dict(side),
        'posSide': dict(posSide),
        'quality_order': summarize_pnl(ord_net),
        'equity_order': equity_metrics(ord_net)
    }

    # per symbol bills table
    sym_bill=[]
    for sym,v in by_symbol_bill.items():
        sym_bill.append({'instId': sym, **v})
    sym_bill.sort(key=lambda x: x.get('net',0.0), reverse=True)

    coverage={
        'raw_dir': raw,
        'instIds': inst_ids,
        'bills_rows': len(bills),
        'fills_rows': len(fill_rows),
        'orders_rows': len(order_rows),
        'time_range_cn': {
            'start': (min(bill_times).astimezone(CN_TZ).isoformat() if bill_times else None),
            'end': (max(bill_times).astimezone(CN_TZ).isoformat() if bill_times else None)
        }
    }

    analysis={
        'coverage': coverage,
        'bills_summary': bills_summary,
        'fills_summary': fills_summary,
        'orders_summary': orders_summary,
        'by_instrument_bills': sym_bill
    }

    with open(os.path.join(out,'analysis.json'),'w',encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

if __name__=='__main__':
    main()
