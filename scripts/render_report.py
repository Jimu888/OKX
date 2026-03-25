import argparse, json, os, math
from datetime import datetime, timedelta, timezone

CN_TZ = timezone(timedelta(hours=8))
WD = ['周一','周二','周三','周四','周五','周六','周日']

def fmt_money(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return str(x)

def fmt_pct(x):
    try:
        return f"{float(x)*100:.2f}%"
    except Exception:
        return str(x)

def iso_to_cn(iso):
    if not iso:
        return 'N/A'
    dt = datetime.fromisoformat(iso)
    return dt.astimezone(CN_TZ).strftime('%Y-%m-%d %H:%M')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--out', required=True)
    args=ap.parse_args()

    with open(args.analysis,'r',encoding='utf-8') as f:
        d=json.load(f)

    cov=d['coverage']
    bills=d['bills_summary']
    fills=d['fills_summary']
    orders=d['orders_summary']
    by_inst=d['by_instrument_bills']

    start_cn = cov.get('time_range_cn',{}).get('start')
    end_cn = cov.get('time_range_cn',{}).get('end')
    if start_cn:
        start_cn = datetime.fromisoformat(start_cn).strftime('%Y-%m-%d %H:%M')
    else:
        start_cn = 'N/A'
    if end_cn:
        end_cn = datetime.fromisoformat(end_cn).strftime('%Y-%m-%d %H:%M')
    else:
        end_cn = 'N/A'

    insts = ', '.join(cov.get('instIds') or [])

    lines=[]
    lines.append('# OKX CEX 合约交易分析报告（全面版）')
    lines.append('')
    lines.append('## 0）数据覆盖与口径说明')
    lines.append(f'- 覆盖时间：{start_cn} ～ {end_cn}（北京时间）')
    lines.append('- 覆盖市场：永续合约（SWAP）')
    lines.append(f'- 覆盖品种：{insts if insts else "无"}')
    lines.append(f'- 记录规模：bills {cov.get("bills_rows",0)} 条；fills {cov.get("fills_rows",0)} 条；orders {cov.get("orders_rows",0)} 条')
    lines.append('')
    lines.append('口径说明：')
    lines.append('- **盈亏/手续费/资金费**：以 bills（账单流水）为准（最接近真实资金变动）。')
    lines.append('- **订单口径**：orders-history 用于统计订单类型/方向/成交状态，并用订单 pnl+fee 作为交易质量口径。')
    lines.append('- **逐笔口径**：fills 的 fillPnl+fee 更适合看频率、时段分布、连亏结构，但噪声更大。')
    lines.append('')

    lines.append('## 1）硬数据层（客观指标）')
    lines.append(f'- 净收益（bills）：{fmt_money(bills.get("net_total",0))} USDT')
    lines.append(f'- 已实现盈亏（bills）：{fmt_money(bills.get("pnl_total",0))} USDT')
    lines.append(f'- 手续费（bills）：{fmt_money(bills.get("fee_total",0))} USDT')
    lines.append(f'- 资金费（估算，bills type=8）：{fmt_money(bills.get("funding_est",0))} USDT')
    lines.append('')
    lines.append(f'- 活跃交易日（fills）：{fills.get("active_days",0)} 天')
    lines.append(f'- 成交笔数（fills）：{fills.get("rows",0)} 笔')
    lines.append(f'- 活跃日内日均交易频次：{fills.get("trades_per_active_day",0):.1f} 笔/天')
    lines.append('')

    q_ord=orders.get('quality_order',{})
    e_ord=orders.get('equity_order',{})
    q_fill=fills.get('quality_fill',{})
    e_fill=fills.get('equity_fill',{})

    lines.append('### 1.1 交易质量（订单口径，参考）')
    lines.append(f'- 胜率：{fmt_pct(q_ord.get("win_rate",0))}')
    lines.append(f'- 盈亏比RR：{(q_ord.get("rr",0) if math.isfinite(q_ord.get("rr",0)) else 0):.2f}')
    lines.append(f'- Profit Factor：{(q_ord.get("profit_factor",0) if math.isfinite(q_ord.get("profit_factor",0)) else 0):.2f}')
    lines.append(f'- 最大连续盈利单数：{e_ord.get("max_consecutive_win",0)}')
    lines.append(f'- 最大连续亏损单数：{e_ord.get("max_consecutive_loss",0)}')
    lines.append(f'- 最大回撤估算（订单净值曲线）：{fmt_money(e_ord.get("max_drawdown",0))} USDT')
    lines.append('')

    lines.append('### 1.2 行为证据（逐笔口径）')
    lines.append(f'- 胜率：{fmt_pct(q_fill.get("win_rate",0))}')
    lines.append(f'- 盈亏比RR：{(q_fill.get("rr",0) if math.isfinite(q_fill.get("rr",0)) else 0):.2f}')
    lines.append(f'- Profit Factor：{(q_fill.get("profit_factor",0) if math.isfinite(q_fill.get("profit_factor",0)) else 0):.2f}')
    lines.append(f'- 最大连续亏损笔数：{e_fill.get("max_consecutive_loss",0)}')
    lines.append(f'- 最大回撤估算（逐笔净值曲线）：{fmt_money(e_fill.get("max_drawdown",0))} USDT')
    lines.append('')

    lines.append('## 2）品种维度（bills 资金口径）')
    lines.append('> 以下净收益为 bills 口径，更接近真实资金结果。')
    lines.append('')
    lines.append('- 品种净收益 / 已实现盈亏 / 手续费 / 记录条数：')
    for row in by_inst:
        lines.append(f'  - {row.get("instId")}: 净 {fmt_money(row.get("net",0))} / 盈亏 {fmt_money(row.get("pnl",0))} / 手续费 {fmt_money(row.get("fee",0))} / {row.get("n",0)} 条')
    lines.append('')

    lines.append('## 3）时间维度（逐笔口径）')
    by_hour=fills.get('by_hour_cn',{})
    lines.append('### 3.1 时段（北京时间小时）')
    for h in sorted(by_hour.keys(), key=lambda x:int(x)):
        v=by_hour[h]
        lines.append(f'- {int(h):02d}:00：净 {fmt_money(v.get("net",0))} USDT（{v.get("n",0)} 笔）')
    lines.append('')
    by_wday=fills.get('by_wday_cn',{})
    lines.append('### 3.2 星期（北京时间）')
    for k in sorted(by_wday.keys(), key=lambda x:int(x)):
        v=by_wday[k]
        lines.append(f'- {WD[int(k)]}：净 {fmt_money(v.get("net",0))} USDT（{v.get("n",0)} 笔）')
    lines.append('')

    lines.append('## 4）订单维度（交易习惯）')
    lines.append(f'- 订单总数：{orders.get("rows",0)}')
    def fmt_counter(c):
        return '；'.join([f'{k}:{v}' for k,v in c.items()]) if c else '无'
    lines.append(f'- 订单状态分布：{fmt_counter(orders.get("state",{}))}')
    lines.append(f'- 订单类型分布：{fmt_counter(orders.get("ordType",{}))}')
    lines.append(f'- 买卖方向分布：{fmt_counter(orders.get("side",{}))}')
    lines.append(f'- 持仓方向分布：{fmt_counter(orders.get("posSide",{}))}')
    lines.append('')

    lines.append('## 5）行为模式识别（客观信号）')
    if fills.get('active_days',0) and fills.get('trades_per_active_day',0) >= 50:
        lines.append('- 高频/冲动交易信号：明显（活跃天数少，但单日成交密度很高）')
    elif fills.get('active_days',0) and fills.get('trades_per_active_day',0) >= 20:
        lines.append('- 高频交易信号：偏高')
    else:
        lines.append('- 高频交易信号：一般')

    denom=abs(bills.get('pnl_total',0)) if abs(bills.get('pnl_total',0))>1e-9 else 1.0
    fee_ratio=abs(bills.get('fee_total',0))/denom
    lines.append(f'- 成本侵蚀：手续费/已实现盈亏 ≈ {fee_ratio*100:.1f}%（越高越容易“方向对了也赚不到钱”）')
    lines.append('- 品种结构：样本期集中于少数品种（见上方品种表）')

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out,'REPORT.md'),'w',encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

if __name__=='__main__':
    main()
