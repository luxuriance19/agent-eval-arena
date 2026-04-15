# Claude Code 配置

## 模型

保持当前配置不变。CC 使用自身默认的模型配置。

## 执行命令

```bash
claude --print --permission-mode bypassPermissions "<prompt>"
```

带 JSON 输出（获取 token 统计）:
```bash
claude --print --permission-mode bypassPermissions --output-format json "<prompt>"
```

## 浏览器

通过 `agent-browser` skill 使用，已安装 v0.16.3。

## 工作目录

每个任务在 `results/cc/<cat>/` 下独立子目录执行。
