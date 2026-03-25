# TradeMate

_Built with OKX Agent Trade Kit_

One-command pipeline powered by the official OKX Agent Trade Kit to:
- Export OKX CEX trade history (contracts: SWAP/FUTURES)
- Analyze behavior/performance
- Generate an objective report, an agent writing task, and a final letter webpage

## What TradeMate Is

TradeMate 不是一个交易信号工具，也不是一个下单助手，而是一个基于 OKX Agent Trade Kit 构建的交易陪伴系统。

它读取你的历史交易数据，识别行为模式、风险来源和优势场景，再通过 Agent 生成一份可持续追问、可持续复盘、可持续成长的个性化总结。

说得更简单一点：TradeMate 帮你了解自己的交易行为和习惯，并陪伴和帮助你成长。

它不帮你更快地下单，而是帮助你看清自己是如何交易的。它会把用户的历史订单、成交、盈亏和成本数据进行统一处理，进一步识别交易风格、重复错误、风险来源与优势场景，再通过 Agent 生成一份可追问、可复盘、可持续成长的阶段总结。

很多交易产品在分析市场，TradeMate 在分析交易者本人。

它不只是告诉你赚了还是亏了，而是进一步回答：

- 我在交易里真正擅长的是什么，不擅长什么？
- 我在哪类资产、哪类节奏、哪类市场环境下表现更好？
- 我平时更像哪种交易者：波段型、冲动型、趋势型，还是别的类型？
- 我的亏损主要来自哪里？
- 哪些交易真的在为我赚钱，哪些交易只是在制造忙碌感？
- 我有哪些优势还没有被稳定发挥出来？

TradeMate 也不是给你一堆冰冷数据。它会把分析结果整理成一份更温暖的内容，真正像一个朋友一样和你聊聊交易。

Agent 的价值，不该只是把“下单”这件事做得更快，而是要把“理解交易、总结行为、持续陪伴、帮助成长”这件事做得更自然、更个性化。未来的 AI 交易产品，不只是执行工具，更是本就孤独的交易者身边最贴心的小伙伴。

## Quick start

1) Configure your OKX API credentials in `~/.okx/config.toml` so the official OKX Agent Trade Kit can read them.

配置文件路径：

- Windows: `C:\Users\<你的用户名>\.okx\config.toml`
- macOS: `~/.okx/config.toml`

如果你是第一次使用，建议先看这两份中文教程：

- `docs/start-here.md`
- `docs/okx-api-setup.md`
- `docs/config-setup.md`

如果是发给普通用户，建议 agent 直接发送 GitHub 教程链接：

- `https://github.com/Jimu888/OKX/blob/main/docs/start-here.md`
- `https://github.com/Jimu888/OKX/blob/main/docs/okx-api-setup.md`
- `https://github.com/Jimu888/OKX/blob/main/docs/config-setup.md`

重要提醒：

- 这个项目会通过官方 OKX Agent Trade Kit 读取历史交易数据
- 创建 API Key 时只开启“读取”权限
- 不要开启“交易”权限
- 不要开启“提币”权限
- 不建议把 API Key 直接发给 agent
- 更推荐由你自己写入 `~/.okx/config.toml`，再由官方 OKX Agent Trade Kit 读取

如果你想让 agent 直接引导用户，最推荐先让用户打开：

- `docs/start-here.md`

2) Run the pipeline:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1 -Profile live -Days 60 -Name 澜
```

macOS 如果已安装 PowerShell 7，也可以使用：

```bash
pwsh -NoProfile -File ./scripts/run_pipeline.ps1 -Profile live -Days 60 -Name 澜
```

3) After the pipeline finishes, ask your agent to open:

- `runs/<timestamp>/output/LETTER_PROMPT.md`

and follow that instruction to write:

- `runs/<timestamp>/output/LETTER.md`

4) Then render the final webpage:

```powershell
python .\scripts\render_letter_html.py --analysis .\runs\<timestamp>\analysis\analysis.json --template .\assets\letter-version.template.html --letter-md .\runs\<timestamp>\output\LETTER.md --out .\runs\<timestamp>\output
```

Outputs are written to:

- `runs/<timestamp>/analysis/analysis.json`
- `runs/<timestamp>/output/REPORT.md`
- `runs/<timestamp>/output/LETTER_PROMPT.md`
- `runs/<timestamp>/output/LETTER.md`
- `runs/<timestamp>/output/result-pages/letter-version.html`

## Notes

- This tool clears `OKX_*` environment variables for the process so they cannot override `~/.okx/config.toml`.
- The letter itself is meant to be written by the user's agent based on `REPORT.md` and `LETTER_PROMPT.md`.
- The HTML template controls style and layout only. The page text should come from `LETTER.md`.
- Windows 与 macOS 都可以使用；差异主要在配置文件路径和启动命令。
