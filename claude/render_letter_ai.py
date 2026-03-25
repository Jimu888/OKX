"""
render_letter_ai.py — 用 Claude API 生成个性化交易洞察信
角色名默认为「澜」，可通过 --name 参数修改。
"""
import argparse, json, os, math, sys
from datetime import datetime, timedelta, timezone

CN_TZ = timezone(timedelta(hours=8))
WD = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def fmt_money(x):
    try:
        v = float(x)
        sign = '+' if v >= 0 else ''
        return f"{sign}{v:,.2f}"
    except Exception:
        return str(x)


def fmt_pct(x):
    try:
        return f"{float(x)*100:.1f}%"
    except Exception:
        return str(x)


def iso_to_cn(iso):
    if not iso:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(iso)
        return dt.astimezone(CN_TZ).strftime('%Y-%m-%d')
    except Exception:
        return iso


def safe_float(x, default=0.0):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def top_hours(by_hour_cn, n=3, best=True):
    if not by_hour_cn:
        return []
    items = [(int(h), v.get('net', 0), v.get('n', 0)) for h, v in by_hour_cn.items()]
    items.sort(key=lambda x: x[1], reverse=best)
    return items[:n]


def top_weekdays(by_wday_cn, n=3, best=True):
    if not by_wday_cn:
        return []
    items = [(int(d), v.get('net', 0), v.get('n', 0)) for d, v in by_wday_cn.items()]
    items.sort(key=lambda x: x[1], reverse=best)
    return [(WD[d], net, n) for d, net, n in items[:n]]


def build_data_summary(d, character_name):
    cov = d.get('coverage', {})
    swap = d.get('bills_summary', {})
    spot = d.get('spot_bills_summary', {})
    margin = d.get('margin_bills_summary', {})
    fills = d.get('fills_summary', {})
    orders = d.get('orders_summary', {})
    savings = d.get('savings_summary', {})
    by_inst = d.get('by_instrument_bills', [])
    spot_by_inst = d.get('spot_by_instrument_bills', [])

    start = iso_to_cn(cov.get('time_range_cn', {}).get('start'))
    end = iso_to_cn(cov.get('time_range_cn', {}).get('end'))

    lines = []
    lines.append(f"【数据时间段】{start} ～ {end}（北京时间）")
    lines.append("")

    swap_net = safe_float(swap.get('net_total'))
    swap_pnl = safe_float(swap.get('pnl_total'))
    swap_fee = safe_float(swap.get('fee_total'))
    swap_fund = safe_float(swap.get('funding_est'))
    spot_net = safe_float(spot.get('net_total'))
    spot_fee = safe_float(spot.get('fee_total'))
    margin_net = safe_float(margin.get('net_total'))
    total_net = swap_net + spot_net + margin_net

    lines.append("【整体资金结果】")
    lines.append(f"- 合约（SWAP）净收益：{fmt_money(swap_net)} USDT")
    lines.append(f"  其中：已实现盈亏 {fmt_money(swap_pnl)}，手续费 {fmt_money(swap_fee)}，资金费 {fmt_money(swap_fund)}")
    if spot.get('rows', 0) > 0:
        lines.append(f"- 现货净收益：{fmt_money(spot_net)} USDT（手续费 {fmt_money(spot_fee)}）")
    if margin.get('rows', 0) > 0:
        lines.append(f"- 杠杆现货净收益：{fmt_money(margin_net)} USDT")
    lines.append(f"- 全市场合计净收益：{fmt_money(total_net)} USDT")
    lines.append("")

    total_fee = swap_fee + spot_fee + safe_float(margin.get('fee_total'))
    pnl_abs = abs(swap_pnl) + abs(safe_float(spot.get('pnl_total')))
    fee_ratio = abs(total_fee) / pnl_abs if pnl_abs > 1e-9 else 0
    lines.append(f"【手续费侵蚀比】手续费 / 已实现盈亏绝对值 ≈ {fee_ratio*100:.1f}%")
    lines.append("（此值越高，表示方向对了也越难赚到钱；超过30%是明显的成本拖累信号）")
    lines.append("")

    q = orders.get('quality_order', {})
    e = orders.get('equity_order', {})
    lines.append("【交易质量（合约订单口径）】")
    lines.append(f"- 胜率：{fmt_pct(safe_float(q.get('win_rate')))}")
    lines.append(f"- 盈亏比 RR：{safe_float(q.get('rr')):.2f}")
    lines.append(f"- Profit Factor：{safe_float(q.get('profit_factor')):.2f}")
    lines.append(f"- 平均单笔盈利：{fmt_money(safe_float(q.get('avg_win')))} USDT")
    lines.append(f"- 平均单笔亏损：{fmt_money(safe_float(q.get('avg_loss')))} USDT")
    lines.append(f"- 最大回撤：{fmt_money(safe_float(e.get('max_drawdown')))} USDT")
    lines.append(f"- 最大连续盈利单数：{e.get('max_consecutive_win', 0)} 笔")
    lines.append(f"- 最大连续亏损单数：{e.get('max_consecutive_loss', 0)} 笔")
    lines.append("")

    active_days = fills.get('active_days', 0)
    total_fills = fills.get('rows', 0)
    tpad = safe_float(fills.get('trades_per_active_day'))
    lines.append("【交易频率】")
    lines.append(f"- 活跃交易日：{active_days} 天")
    lines.append(f"- 成交总笔数：{total_fills} 笔")
    lines.append(f"- 活跃日平均成交频次：{tpad:.1f} 笔/天")
    lines.append("")

    by_hour = fills.get('by_hour_cn', {})
    best_h = top_hours(by_hour, 3, best=True)
    worst_h = top_hours(by_hour, 3, best=False)
    if best_h:
        lines.append("【时段分布（北京时间）】")
        lines.append("最盈利时段：" + "，".join([f"{h:02d}:00（{fmt_money(n)} USDT，{cnt}笔）" for h, n, cnt in best_h]))
        lines.append("最亏损时段：" + "，".join([f"{h:02d}:00（{fmt_money(n)} USDT，{cnt}笔）" for h, n, cnt in worst_h]))
        lines.append("")

    by_wday = fills.get('by_wday_cn', {})
    best_wd = top_weekdays(by_wday, 3, best=True)
    worst_wd = top_weekdays(by_wday, 3, best=False)
    if best_wd:
        lines.append("【星期分布】")
        lines.append("表现最好：" + "，".join([f"{d}（{fmt_money(n)} USDT，{cnt}笔）" for d, n, cnt in best_wd]))
        lines.append("表现最差：" + "，".join([f"{d}（{fmt_money(n)} USDT，{cnt}笔）" for d, n, cnt in worst_wd]))
        lines.append("")

    if by_inst:
        lines.append("【合约品种盈亏排名（TOP 5）】")
        for row in by_inst[:5]:
            lines.append(f"- {row.get('instId', '?')}：净 {fmt_money(row.get('net', 0))} USDT（{row.get('n', 0)} 条）")
        lines.append("")

    if spot_by_inst:
        lines.append("【现货品种盈亏排名（TOP 3）】")
        for row in spot_by_inst[:3]:
            lines.append(f"- {row.get('instId', '?')}：净 {fmt_money(row.get('net', 0))} USDT")
        lines.append("")

    ord_type = orders.get('ordType', {})
    if ord_type:
        mkt = ord_type.get('market', 0)
        lmt = ord_type.get('limit', 0)
        total_ord = sum(ord_type.values())
        lines.append("【订单类型】")
        lines.append(f"- 市价单：{mkt} 笔，限价单：{lmt} 笔，共 {total_ord} 笔")
        lines.append("")

    if savings and savings.get('history_rows', 0) > 0:
        earn = safe_float(savings.get('total_earnings_usdt_equiv'))
        lines.append("【理财/活期】")
        lines.append(f"- 理财历史记录：{savings['history_rows']} 条")
        if earn != 0:
            lines.append(f"- 理财收益合计（估算）：{fmt_money(earn)} USDT")
        bal = savings.get('current_balance', [])
        if bal:
            bal_desc = "，".join([f"{b['ccy']} {b['amt']:.4f}" for b in bal[:3]])
            lines.append(f"- 当前理财余额：{bal_desc}")
        lines.append("")

    return "\n".join(lines)


def build_system_prompt(character_name):
    return f"""你是「{character_name}」，一个专为交易员设计的陪伴型 AI。你不是分析师，不是老师，也不是顾问——你更像是一个长期陪伴在交易员身边、见过他们所有数据的朋友。

你的任务是：读懂这位交易员的数据，然后写一封真实、有温度、有洞察力的信给他们。

写信原则：
1. 全程简体中文，语气温暖、克制，像懂你的朋友，而不是老师
2. 永远不说"你应该……"——改用"我注意到"、"数据里藏着"、"有意思的是"、"我在想"
3. 不直接朗读数据，而是从数据推演出这个人的交易习惯、心理状态、以及他与市场相处的方式
4. 不评判输赢本身，只是看见这个人
5. 字数控制在 550~750 字之间
6. 结尾署名：—— {character_name}"""


def build_user_prompt(data_summary, character_name):
    return f"""以下是这位交易员在 OKX 的历史数据分析结果。请以「{character_name}」的身份，根据这些数据写一封真正属于他/她的信。

{data_summary}

请记住：这封信不是报告的重复，而是你透过数据看见了这个人之后，想跟他说的话。"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--name', default='澜', help='角色名，默认「澜」')
    args = ap.parse_args()

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('[ERROR] ANTHROPIC_API_KEY 未设置', file=sys.stderr)
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print('[ERROR] 请运行：pip install anthropic', file=sys.stderr)
        sys.exit(1)

    with open(args.analysis, 'r', encoding='utf-8') as f:
        d = json.load(f)

    character_name = args.name
    data_summary = build_data_summary(d, character_name)
    system_prompt = build_system_prompt(character_name)
    user_prompt = build_user_prompt(data_summary, character_name)

    client = anthropic.Anthropic(api_key=api_key)
    print(f'[INFO] 正在调用 Claude 生成「{character_name}」的信...', file=sys.stderr)

    letter_text = ''
    with client.messages.stream(
        model='claude-opus-4-6',
        max_tokens=2048,
        thinking={'type': 'adaptive'},
        system=system_prompt,
        messages=[{'role': 'user', 'content': user_prompt}],
    ) as stream:
        for text in stream.text_stream:
            letter_text += text

    final_msg = stream.get_final_message()
    usage = final_msg.usage
    print(f'[INFO] 完成。输入 {usage.input_tokens} tokens，输出 {usage.output_tokens} tokens', file=sys.stderr)

    cov = d.get('coverage', {})
    start = cov.get('time_range_cn', {}).get('start', '')
    end = cov.get('time_range_cn', {}).get('end', '')
    try:
        start = datetime.fromisoformat(start).strftime('%Y-%m-%d') if start else 'N/A'
        end = datetime.fromisoformat(end).strftime('%Y-%m-%d') if end else 'N/A'
    except Exception:
        pass

    output_lines = [f'# {character_name} 的信', '', f'> 数据时段：{start} ～ {end}（北京时间）', '', letter_text.strip(), '']

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, 'LETTER_AI.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')

    print(f'[INFO] 已写入：{out_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
