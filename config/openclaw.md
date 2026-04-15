# OpenClaw 配置

## 模型

已配置好，无需修改。使用 baidu-int 代理:

- Provider: `openai-completions`
- BaseURL: `http://api.dbh.baidu-int.com`
- Model: `claude-sonnet-4-5-20250929`
- 配置文件: `~/.openclaw/openclaw.json`

## 执行命令

```bash
cd /Users/lini03/baidu/clawdbot
node openclaw.mjs agent --local --message "<prompt>" --thinking high
```

## 浏览器

- 内置: `extensions/browser/` (Playwright + CDP)
- Skill: `skills/agent-browser/`

## 工作目录

每个任务在 `results/openclaw/<cat>/` 下独立子目录执行。
需要通过 `--cwd` 或在 prompt 中指定工作目录。
