# 新手开始这里

这份入口页是给使用官方 OKX Agent Trade Kit 的用户看的。

如果你是第一次使用这个项目，建议先按下面顺序操作。

## 第 1 步：先看 API 创建教程

请先阅读：

- GitHub 页面：
  `https://github.com/Jimu888/OKX/blob/main/docs/okx-api-setup.md`
- 仓库文件：
  `docs/okx-api-setup.md`

这里会教你：

- 如何在 OKX 网页版创建 API Key
- 如何在 OKX 手机 App 创建 API Key
- 如何确保只开启“读取”权限
- 为什么这些凭证要写入 `~/.okx/config.toml`，让官方 OKX Agent Trade Kit 读取

重要提醒：

- 只开启“读取”权限
- 不要开启“交易”权限
- 不要开启“提币”权限

## 第 2 步：再看配置文件填写教程

请继续阅读：

- GitHub 页面：
  `https://github.com/Jimu888/OKX/blob/main/docs/config-setup.md`
- 仓库文件：
  `docs/config-setup.md`

这里会教你：

- API Key 应该保存到哪里
- Windows 用户应该写到哪个路径
- macOS 用户应该写到哪个路径
- 如何填写 `~/.okx/config.toml`
- 为什么要让官方 OKX Agent Trade Kit 从配置文件读取，而不是把 key 直接发给 agent

## 第 3 步：不要直接把 API Key 发给 agent

推荐做法：

1. 自己先创建只读 API Key
2. 自己把它保存进配置文件
3. 再告诉 agent 继续

推荐对 agent 说：

```text
我已经看过教程，并把 OKX API Key 保存到配置文件里了，你可以继续帮我执行后面的数据抓取、分析和网页生成。
```

如果需要点明取数方式，可以补一句：

```text
请使用官方 OKX Agent Trade Kit 读取这些配置继续执行。
```

## 第 4 步：开始运行

如果你希望 agent 在第一次引导时直接给出一个统一入口，最适合发送这个链接：

- `https://github.com/Jimu888/OKX/blob/main/docs/start-here.md`

准备好之后，再运行项目流程。

Windows 示例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1 -Profile live -Days 90 -Name 澜
```

macOS 示例（已安装 PowerShell 7）：

```bash
pwsh -NoProfile -File ./scripts/run_pipeline.ps1 -Profile live -Days 90 -Name 澜
```
