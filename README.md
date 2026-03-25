# OKX Trade History Analyzer (Agent Trade Kit)

One-command pipeline to:
- Export OKX CEX trade history (contracts: SWAP/FUTURES)
- Analyze behavior/performance
- Generate an objective report, an agent writing task, and a final letter webpage

## Quick start

1) Configure your OKX API credentials in `~/.okx/config.toml` (Agent Trade Kit profile format).

2) Run the pipeline:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1 -Profile live -Days 90 -Name 澜
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
