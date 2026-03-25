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

## Prerequisites (user)

- The user needs OKX API credentials with read permissions
- Credentials should be stored in:
  - Windows: `C:\Users\<you>\.okx\config.toml`
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

## Run (local / agent-controlled)

Use the PowerShell pipeline script (recommended):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1 -Profile live -Days 90 -Name 澜
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

## When to publish to GitHub

Publishing is optional. If enabled, it will copy the `output/` folder into a chosen repo folder and git commit/push.
See `scripts/publish_github.ps1`.
