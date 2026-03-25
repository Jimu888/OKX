---
name: okx-trade-history-analyzer
description: End-to-end OKX CEX trade history export + analysis + report generation using OKX Agent Trade Kit credentials (~/.okx/config.toml), plus an agent-authored letter and styled HTML page. Use when the user wants their agent to export OKX data, analyze trading behavior, generate a factual report, write a grounded letter from a controlled prompt, and render it as a webpage.
---

# OKX Trade History Analyzer (Agent Trade Kit)

## What this skill does

Runs a full agent-first pipeline:
1) Guide the user to configure OKX API credentials in `~/.okx/config.toml`
2) Export OKX CEX trade history (contracts first: SWAP/FUTURES) into JSONL
3) Analyze and compute metrics (coverage + multi-dimensional stats)
4) Generate:
   - `REPORT.md` (objective report)
   - `LETTER_PROMPT.md` (pre-designed prompt for the agent to write the letter)
5) The agent reads `REPORT.md` and `LETTER_PROMPT.md`, then writes:
   - `LETTER.md`
6) Render the webpage:
   - `result-pages/letter-version.html` (template layout, agent-written text)

All OKX credentials are read from `~/.okx/config.toml` (Agent Trade Kit profile). Do not ask the user for exchange keys in chat unless you are helping them place them into that config file. The letter is written by the user's current agent, not by a hard-coded external model API.

平台兼容要求：

- 这套 skill 要同时兼容 Windows 和 macOS 用户
- 讲解配置路径时，要按用户系统分别说明
- Windows 路径：`C:\Users\<用户名>\.okx\config.toml`
- macOS 路径：`~/.okx/config.toml`
- 如果用户在 macOS 上安装了 PowerShell 7，可以直接运行 `run_pipeline.ps1`
- 如果用户没有 PowerShell 7，agent 应自行按步骤调用 Node 与 Python 脚本完成同样流程

## 首次使用时的主动引导

当用户第一次安装或调用这个 skill 时，agent 应主动检查 `~/.okx/config.toml` 是否存在。

如果配置文件不存在，不要立刻运行抓数脚本，而是先进入引导流程。

你应该主动告诉用户：

- 这个项目只读取历史交易数据
- 这个 API Key 不用于下单
- 这个 API Key 不用于提币
- 创建 API 时只需要开启“读取”权限
- 不要开启“交易”权限
- 不要开启“提币”权限
- 不建议把 API Key 直接发给 agent
- 更推荐由用户自行保存到 `~/.okx/config.toml`

推荐引导文案：

```text
在开始分析前，我先帮你完成 OKX API 配置。

这个 skill 只会读取你的历史交易数据，不会帮你下单，也不能提币。为了安全起见，请你创建一个只开启“读取”权限的 OKX API Key，不要开启“交易”或“提币”。

创建完成后，不用把 API Key 直接发给我。你只需要把它保存到 `~/.okx/config.toml`，我再继续帮你抓取数据、生成报告和网页。
```

引导用户时，优先让他们查看：

- `docs/start-here.md`
- `docs/okx-api-setup.md`
- `docs/config-setup.md`

如果要给用户一个统一入口，优先推荐 `docs/start-here.md`。

## Prerequisites (user)

- The user needs OKX API credentials with read permissions
- Credentials should be stored in:
  - Windows: `C:\Users\<you>\.okx\config.toml`
  - macOS: `~/.okx/config.toml`
- Node.js >= 18
- Python 3.10+

## Required behavior for the agent

When the user installs or invokes this skill, you should:

1. Help the user set up `~/.okx/config.toml` if it is missing
2. Explain what values are needed:
   - API key
   - secret key
   - passphrase
   - profile name
3. Run the pipeline script
4. Read the generated `REPORT.md` and `LETTER_PROMPT.md`
5. Write `LETTER.md` yourself following the prompt strictly
6. Run the HTML renderer so the page text comes from `LETTER.md`
7. Tell the user exactly where the report and webpage were written
8. If your environment supports it, open the final HTML page for the user

补充要求：

- 如果用户还没有 API Key，先引导他们去创建只读 API
- 如果用户已经有 API Key，不要要求他们把 key 直接发给你
- 优先引导用户把 key 保存进 `~/.okx/config.toml`
- 在确认配置文件已准备好之前，不要启动导出流程
- 如果用户是 macOS，说明配置文件路径应写到 `~/.okx/config.toml`
- 如果用户是 Windows，说明配置文件路径应写到 `C:\Users\<用户名>\.okx\config.toml`

## Run (local / agent-controlled)

Use the PowerShell pipeline script (recommended):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1 -Profile live -Days 90 -Name 澜
```

For macOS users with PowerShell 7:

```bash
pwsh -NoProfile -File ./scripts/run_pipeline.ps1 -Profile live -Days 90 -Name 澜
```

Outputs are written under:

- `runs/<timestamp>/raw/` (exported JSONL)
- `runs/<timestamp>/analysis/` (analysis.json)
- `runs/<timestamp>/output/REPORT.md`
- `runs/<timestamp>/output/LETTER_PROMPT.md`
- `runs/<timestamp>/output/LETTER.md`
- `runs/<timestamp>/output/result-pages/letter-version.html`

## How the letter should be produced

- The agent must not reuse an old canned letter template
- The agent must base the letter on the generated `REPORT.md` and `analysis.json`
- The letter should follow the style and constraints embedded in `LETTER_PROMPT.md`
- The HTML template is for visual style only; it must not override the agent-written text

## Final rendering step

After `LETTER.md` is written, render the webpage with:

```powershell
python .\scripts\render_letter_html.py --analysis .\runs\<timestamp>\analysis\analysis.json --template .\assets\letter-version.template.html --letter-md .\runs\<timestamp>\output\LETTER.md --out .\runs\<timestamp>\output
```

## Notes / safety

- The pipeline clears `OKX_*` environment variables for the process so they cannot override `~/.okx/config.toml`.
- Default mode is read-only data export + analysis.
- If some endpoints return empty, the report includes a coverage section so results are not over-claimed.
- If the config file is missing, help the user create it before running anything else.
- If the letter has not yet been written, do not pretend the final webpage is complete.
- 反复提醒用户：这个项目只需要只读 API，不需要交易权限，也不需要提币权限。

## When to publish to GitHub

Publishing is optional. If enabled, it will copy the `output/` folder into a chosen repo folder and git commit/push.
See `scripts/publish_github.ps1`.
