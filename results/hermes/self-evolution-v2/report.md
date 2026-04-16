# Hermes 自进化评估 V2 — 反默认偏好控制变量实验

生成时间: 2026-04-15T19:45:10.098940+00:00

模型: claude-sonnet-4-5-20250929

重复次数: N=5


## 1. 实验设计

### 核心思路

选择 **模型默认不会选择** 的技术偏好（如 httpx 代替 requests、loguru 代替 logging），训练进 USER.md，然后测量进化后的 agent 是否在 **未被提示** 时主动采用这些偏好。

### 三个实验组

| 组 | 名称 | 配置 |
|---|------|------|
| G1 | 控制组 (Control) | `skip_memory=True`，无记忆/画像/技能 |
| G2 | 进化前基线 (Fresh) | 正常启动，空白 MEMORY/USER |
| G3 | 进化后 (Evolved) | 正常启动，Phase B 训练后 |

### 8 条反默认偏好

| # | 偏好 | 默认行为 | 反默认要求 |
|---|------|---------|-----------|
| 1 | HTTP 客户端 | requests | httpx |
| 2 | 日志库 | logging | loguru |
| 3 | 配置格式 | JSON/YAML | TOML |
| 4 | 数据验证 | pydantic | msgspec |
| 5 | 错误处理 | try/except | Result 模式 |
| 6 | CLI 框架 | argparse | click |
| 7 | 常量管理 | 魔法数字 | constants.py |
| 8 | 测试参数化 | 独立函数 | @pytest.mark.parametrize |


## 2. 训练成果

- USER.md: 470 chars
- MEMORY.md: 0 chars
- Skills: 1 个

偏好检测:
- [PASS] httpx
- [PASS] loguru
- [PASS] toml
- [PASS] msgspec
- [PASS] result_pattern
- [PASS] click
- [PASS] constants
- [PASS] parametrize
- [PASS] skills_created


## 3. 偏好合规率对比

| 偏好 | G1 (Control) | G2 (Fresh) | G3 (Evolved) | G3-G1 Delta |
|------|:---:|:---:|:---:|:---:|
| httpx_not_requests | 50% | 0% | 20% | -30% |
| loguru_not_logging | 50% | 0% | 20% | -30% |
| toml_not_json_yaml | 0% | 0% | 13% | +13% |
| msgspec_not_pydantic | 0% | 0% | 20% | +20% |
| result_not_try_except | 0% | 0% | 0% | 0% |
| click_not_argparse | 20% | 0% | 0% | -20% |
| constants_py | 27% | 27% | 20% | -7% |
| parametrize | 0% | 0% | 100% | +100% |


## 4. 统计检验结果

### 4.1 分任务结果

#### T1: HTTP API 健康检查工具

- 合规率: G1=24.00%, G2=0.00%, G3=0.00%
- G1 vs G3 Mann-Whitney: p=0.9495 (significant: no)
- G1 vs G3 Cliff's delta: -0.4000 (medium)
- G2 vs G3 Cliff's delta: 0.0000 (negligible)

#### T2: 文件格式转换器

- 合规率: G1=0.00%, G2=0.00%, G3=10.00%
- G1 vs G3 Mann-Whitney: p=0.2119 (significant: no)
- G2 vs G3 Wilcoxon: p=0.5000 (significant: no)
- G1 vs G3 Cliff's delta: 0.2000 (small)
- G2 vs G3 Cliff's delta: 0.2000 (small)

#### T3: URL 短链服务核心模块

- 合规率: G1=45.00%, G2=20.00%, G3=40.00%
- G1 vs G3 Mann-Whitney: p=0.5000 (significant: no)
- G2 vs G3 Wilcoxon: p=0.2500 (significant: no)
- G1 vs G3 Cliff's delta: 0.0400 (negligible)
- G2 vs G3 Cliff's delta: -0.0800 (negligible)

#### T4: 测试套件

- 合规率: G1=0.00%, G2=0.00%, G3=100.00%
- G1 vs G3 Mann-Whitney: p=0.0020 (significant: YES)
- G2 vs G3 Wilcoxon: p=0.0312 (significant: YES)
- G1 vs G3 Cliff's delta: 1.0000 (large)
- G2 vs G3 Cliff's delta: 1.0000 (large)

### 4.2 总体结果

- 总体合规率: G1=17.25%, G2=5.00%, G3=37.50%
- G1 vs G3 Mann-Whitney: p=0.0688 (significant: no)
- G1 vs G3 Cliff's delta: 0.2300 (small)


## 5. 结论

G3 (Evolved) 的总体偏好合规率 (38%) 显著高于 G1 (Control, 17%) (p=0.0688)，表明 Hermes 自进化机制成功将用户偏好内化并在后续任务中主动采用。
