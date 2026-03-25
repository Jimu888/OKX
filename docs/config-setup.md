# 配置文件填写教程

这份教程用于帮助用户把 OKX API 信息保存到本项目指定的配置文件中，而不是直接发给 agent。

## 为什么推荐写入配置文件

很多 agent 默认不愿意直接接收 API Key，这也是更安全的做法。

推荐流程是：

1. 用户自己在 OKX 创建只读 API Key
2. 用户自己把 API Key / Secret / Passphrase 写入本地配置文件
3. agent 只读取配置文件并继续执行分析流程

## 配置文件路径

默认使用：

- Windows: `C:\Users\<你的用户名>\.okx\config.toml`
- macOS: `~/.okx/config.toml`

如果 `.okx` 文件夹不存在，可以先手动创建。

例如：

- Windows 可以创建：`C:\Users\<你的用户名>\.okx\`
- macOS 可以创建：`~/.okx/`

## 第一步：创建配置文件

如果还没有这个文件，请先手动创建：

- Windows: `C:\Users\<你的用户名>\.okx\config.toml`
- macOS: `~/.okx/config.toml`

如果目录不存在，也请先把目录创建出来。

## 第二步：把 API 信息写进去

## 推荐配置示例

```toml
[profiles.live]
api_key = "你的_api_key"
secret_key = "你的_secret_key"
passphrase = "你的_passphrase"
```

如果你想使用别的 profile 名称，也可以改成：

```toml
[profiles.myokx]
api_key = "你的_api_key"
secret_key = "你的_secret_key"
passphrase = "你的_passphrase"
```

之后运行脚本时，把 `-Profile` 改成对应名字即可。

例如：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1 -Profile myokx -Days 90 -Name 澜
```

macOS 如果安装了 PowerShell 7，也可以这样运行：

```bash
pwsh -NoProfile -File ./scripts/run_pipeline.ps1 -Profile myokx -Days 90 -Name 澜
```

## 第三步：保存后再让 agent 继续

当你已经把 API 信息写入配置文件后，再告诉 agent：

```text
我已经把 OKX API 信息保存到 ~/.okx/config.toml（或对应系统路径）了，你可以继续了。
```

这样 agent 就可以继续帮你：

1. 抓取历史交易数据
2. 分析数据
3. 生成报告
4. 生成写信提示词
5. 输出网页版本

## 给用户的安全提醒

- 不要把 API Key 直接发到聊天里
- 不要把带有密钥的配置文件提交到 GitHub
- 只使用只读权限
- 不开启交易权限
- 不开启提币权限

## 给 agent 的推荐引导文案

```text
如果你还没有配置好 OKX API，请不要直接把 key 发给我。

你可以把 API Key、Secret Key 和 Passphrase 保存到：
`~/.okx/config.toml`

保存好之后告诉我一声，我会继续帮你执行后面的数据抓取、分析、报告生成和网页渲染。
```
