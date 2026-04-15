# Hermes Agent 配置

## 模型

需要配置 baidu-int 代理（与 OpenClaw 相同）:

- Provider: OpenAI-compatible
- BaseURL: `http://api.dbh.baidu-int.com`
- Model: `claude-sonnet-4-5-20250929`
- 配置文件: `~/.hermes/config.yaml`

### 配置步骤

```yaml
# ~/.hermes/config.yaml
model:
  default: "openai/claude-sonnet-4-5-20250929"
  provider: "openai"

api_base: "http://api.dbh.baidu-int.com"
api_key: "<same-key-as-openclaw>"
```

> 具体字段名需参照 `cli-config.yaml.example` 确认并调整。

## 执行命令

```bash
hermes-agent --model "openai/claude-sonnet-4-5-20250929" --query "<prompt>" --max_turns 30
```

## 浏览器

通过 `tools/browser_tool.py` 调用 `agent-browser` CLI。
需确保 `agent-browser install` 已执行。

## 工作目录

每个任务在 `results/hermes/<cat>/` 下独立子目录执行。
