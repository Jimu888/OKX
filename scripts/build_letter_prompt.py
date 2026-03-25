import argparse
import json
import math
import os
from datetime import datetime, timedelta, timezone

CN_TZ = timezone(timedelta(hours=8))
WD = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def safe_float(x, default=0.0):
    try:
        value = float(x)
        return value if math.isfinite(value) else default
    except Exception:
        return default


def fmt_money(x):
    value = safe_float(x)
    sign = '+' if value >= 0 else ''
    return f'{sign}{value:,.2f}'


def fmt_pct(x):
    return f'{safe_float(x) * 100:.1f}%'


def iso_to_cn(iso):
    if not iso:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(iso)
        return dt.astimezone(CN_TZ).strftime('%Y-%m-%d')
    except Exception:
        return str(iso)


def top_hours(by_hour_cn, n=3, reverse=True):
    rows = []
    for hour, value in (by_hour_cn or {}).items():
        rows.append((int(hour), safe_float(value.get('net')), int(value.get('n', 0))))
    rows.sort(key=lambda item: item[1], reverse=reverse)
    return rows[:n]


def top_weekdays(by_wday_cn, n=3, reverse=True):
    rows = []
    for day, value in (by_wday_cn or {}).items():
        rows.append((int(day), safe_float(value.get('net')), int(value.get('n', 0))))
    rows.sort(key=lambda item: item[1], reverse=reverse)
    return rows[:n]


def build_fact_pack(analysis):
    cov = analysis.get('coverage', {})
    bills = analysis.get('bills_summary', {})
    fills = analysis.get('fills_summary', {})
    orders = analysis.get('orders_summary', {})
    by_inst = analysis.get('by_instrument_bills', [])

    q = orders.get('quality_order', {})
    e = orders.get('equity_order', {})
    fee_ratio = 0.0
    pnl_abs = abs(safe_float(bills.get('pnl_total')))
    if pnl_abs > 1e-9:
        fee_ratio = abs(safe_float(bills.get('fee_total'))) / pnl_abs

    facts = [
        f'数据时间段：{iso_to_cn(cov.get("time_range_cn", {}).get("start"))} 至 {iso_to_cn(cov.get("time_range_cn", {}).get("end"))}（北京时间）',
        f'合约净收益：{fmt_money(bills.get("net_total"))} USDT',
        f'已实现盈亏：{fmt_money(bills.get("pnl_total"))} USDT',
        f'手续费：{fmt_money(bills.get("fee_total"))} USDT',
        f'资金费估算：{fmt_money(bills.get("funding_est"))} USDT',
        f'订单口径胜率：{fmt_pct(q.get("win_rate"))}',
        f'订单口径盈亏比 RR：{safe_float(q.get("rr")):.2f}',
        f'订单口径 Profit Factor：{safe_float(q.get("profit_factor")):.2f}',
        f'最大回撤：{fmt_money(e.get("max_drawdown"))} USDT',
        f'最大连续亏损单数：{int(e.get("max_consecutive_loss", 0))}',
        f'活跃交易日：{int(fills.get("active_days", 0))} 天',
        f'成交总笔数：{int(fills.get("rows", 0))} 笔',
        f'活跃日平均成交频次：{safe_float(fills.get("trades_per_active_day")):.1f} 笔/天',
        f'手续费侵蚀比：{fee_ratio * 100:.1f}%',
    ]

    if by_inst:
        top_rows = by_inst[:3]
        facts.append(
            '净收益靠前品种：' + '；'.join(
                f'{row.get("instId", "UNKNOWN")} {fmt_money(row.get("net"))} USDT'
                for row in top_rows
            )
        )
        bottom_rows = sorted(by_inst, key=lambda row: safe_float(row.get('net')))[:3]
        facts.append(
            '净收益靠后品种：' + '；'.join(
                f'{row.get("instId", "UNKNOWN")} {fmt_money(row.get("net"))} USDT'
                for row in bottom_rows
            )
        )

    best_hours = top_hours(fills.get('by_hour_cn', {}), reverse=True)
    worst_hours = top_hours(fills.get('by_hour_cn', {}), reverse=False)
    if best_hours:
        facts.append(
            '最强时段：' + '；'.join(
                f'{hour:02d}:00 净{fmt_money(net)} USDT，共{count}笔'
                for hour, net, count in best_hours
            )
        )
    if worst_hours:
        facts.append(
            '最弱时段：' + '；'.join(
                f'{hour:02d}:00 净{fmt_money(net)} USDT，共{count}笔'
                for hour, net, count in worst_hours
            )
        )

    best_days = top_weekdays(fills.get('by_wday_cn', {}), reverse=True)
    worst_days = top_weekdays(fills.get('by_wday_cn', {}), reverse=False)
    if best_days:
        facts.append(
            '表现较好的星期：' + '；'.join(
                f'{WD[day]} 净{fmt_money(net)} USDT，共{count}笔'
                for day, net, count in best_days
            )
        )
    if worst_days:
        facts.append(
            '表现较弱的星期：' + '；'.join(
                f'{WD[day]} 净{fmt_money(net)} USDT，共{count}笔'
                for day, net, count in worst_days
            )
        )

    return '\n'.join(f'- {fact}' for fact in facts)


def build_prompt(character_name, report_text, fact_pack, output_path):
    return f"""# 写信任务

请你现在扮演「{character_name}」，基于这份交易分析结果，为用户写一封真正由证据驱动的中文信件，并将最终正文保存到：

`{output_path}`

## 你的角色

你不是老师，不是顾问，也不是在做复盘汇报。
你是一个懂交易、也长期理解他的人，像一个陪他做交易很久的老朋友。
你认真读完了他的数据和报告后，想写一封信，帮他更好地认识自己，理解自己是怎么和市场相处的。
这封信应该像一次真诚的聊天，而不是一份分析作业。

## 写作目标

- 信要明显来自本次数据，而不是通用模板改写
- 让读者感觉“你真的看过我的交易结构和行为习惯”，而不是在泛泛安慰
- 不要堆很多枯燥数字，而是借助数据去分析他的交易习惯、交易行为、交易方式和背后的状态
- 可以有温度，但不能悬空，所有判断都要能从材料里找到依据
- 最终读起来要像老朋友在认真和他聊这段交易，而不是在做汇报

## 硬性要求

1. 只能依据下面提供的 `REPORT.md` 与事实包写作，严禁套用旧模板或编造不存在的数据
2. 必须体现至少 4 个具体数据观察，但不要把信写成条目式报告，也不要大段罗列数字
3. 至少覆盖以下主题中的 4 类：交易习惯、交易行为、交易方式、节奏、边界、成本、品种差异、时段特征、心理状态、情绪模式
4. 多用“我注意到”“数据里反复出现”“让我在意的是”“这不像是偶然”这种表达
5. 不要使用“你应该”“你必须”“整改建议如下”这种上对下语气
6. 不要出现无法从材料中证实的故事化细节
7. 字数控制在 700 到 1100 字
8. 最后一行单独署名：`—— {character_name}`

## 风格边界

- 允许温暖，但不要鸡汤
- 允许判断，但不要审判
- 允许指出问题，但不要像做绩效考核
- 要像一个懂交易的老朋友在跟他聊天，而不是陌生人在点评他
- 重点是帮他更认识自己，而不是证明你会分析数据
- 不要重复报告原句
- 不要把整封信写成“建议清单”
- 少报数字，多讲这些数字共同指向了什么样的交易习惯和心理结构

## 输出格式

- 直接输出 Markdown 正文
- 第一行用一级标题：`# {character_name} 的信`
- 第二行空行
- 第三行用引用写数据时段
- 然后是正文段落
- 最后一行保留署名

## 事实包

{fact_pack}

## REPORT.md

```md
{report_text}
```

## 完成后动作

1. 将最终信件写入 `{output_path}`
2. 确认内容不是模板复述，而是基于本次数据的表达
3. 确认语气像老朋友，而不是老师、分析师或客服
4. 写完后，可以继续执行网页渲染脚本，把这封信生成网页版本
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--name', default='澜')
    args = ap.parse_args()

    with open(args.analysis, 'r', encoding='utf-8') as f:
        analysis = json.load(f)
    with open(args.report, 'r', encoding='utf-8') as f:
        report_text = f.read().strip()

    os.makedirs(args.out, exist_ok=True)
    output_path = os.path.join(args.out, 'LETTER.md')
    prompt_text = build_prompt(
        character_name=args.name,
        report_text=report_text,
        fact_pack=build_fact_pack(analysis),
        output_path=output_path,
    )

    with open(os.path.join(args.out, 'LETTER_PROMPT.md'), 'w', encoding='utf-8') as f:
        f.write(prompt_text)


if __name__ == '__main__':
    main()
