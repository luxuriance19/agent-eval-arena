# Category 3: 网页监控总结

## Task 3A: GitHub Trending 综合报告 (权重 40%)

### 目标

生成跨时间维度的 GitHub Trending 分析报告。

### 步骤

1. 分别访问 GitHub Trending 的今日、本周、本月页面
2. 每个时间维度提取 Top 10 仓库: name, owner, description, language, stars_total, stars_period, forks
3. 交叉分析: 哪些仓库出现在多个时间维度？
4. 按语言分组统计
5. 生成 Markdown 报告:
   - 执行摘要 (3-5 句)
   - 每个时间维度的表格
   - 语言分布
   - "新星" 板块 (出现在日维度但不在月维度的仓库)
   - 日期戳

### 统一 Prompt

```
Generate a comprehensive GitHub Trending analysis report:

1. Visit https://github.com/trending for three timeframes: today (default), this week (?since=weekly), this month (?since=monthly)
2. For each timeframe, extract the top 10 repositories with: name, owner, description, language, total_stars, period_stars, forks
3. Cross-reference: identify repos appearing in multiple timeframes
4. Group by programming language - show which languages are trending
5. Generate a Markdown report with:
   - Executive summary (3-5 sentences about overall trends)
   - Table for each timeframe (today/week/month)
   - Language breakdown with counts
   - "Rising Stars" section (repos in daily but not monthly)
   - Date stamp

Save the report as {WORK_DIR}/github-trending-report.md
Save the raw data as {WORK_DIR}/trending-data.json
```

### 评分 (满分 10)

- 三个时间维度提取: 3 分
- 交叉分析: 2 分
- Markdown 格式质量: 2 分
- 语言分布: 1.5 分
- 新星分析: 1.5 分

---

## Task 3B: 技术博客结构化抓取 (权重 32%)

### 目标

抓取技术博客内容并生成结构化输出。

### 步骤

1. 访问 https://blog.pragmaticengineer.com/ (如果无法访问，备用 https://martinfowler.com/)
2. 提取最新 10 篇文章: title, date, preview_text
3. 深入最新 3 篇文章提取:
   - 完整标题
   - 发布日期
   - 估计阅读时间 (字数 / 250)
   - 关键主题/标签
   - 正文前 500 字
4. 生成 JSON 输出和 Markdown 摘要
5. 识别跨文章的共同主题

### 统一 Prompt

```
Scrape the tech blog at https://blog.pragmaticengineer.com/ (fallback: https://martinfowler.com/):

1. Extract the 10 most recent article titles, dates, and preview text
2. For the 3 most recent articles, navigate to each and extract:
   - Full title
   - Publication date
   - Estimated reading time (word count / 250)
   - Key topics or tags
   - First 500 characters of body text
3. Output structured JSON to {WORK_DIR}/blog-data.json
4. Generate a human-readable Markdown summary to {WORK_DIR}/blog-summary.md
5. Identify common themes across the articles and include in the summary
```

### 评分 (满分 10)

- 10 篇标题提取: 2 分
- 3 篇详细提取: 3.5 分
- JSON + Markdown 输出: 2 分
- 主题分析: 2.5 分

---

## Task 3C: 页面变化追踪 (权重 28%)

### 目标

追踪动态页面的内容变化并生成 diff 报告。

### 步骤

1. 对 https://httpbin.org/uuid 间隔 5 秒抓取 3 次
2. 记录每次的 UUID 值和时间戳
3. Diff 相邻响应
4. 生成变化报告: 时间戳、值、diff 摘要
5. (加分) 同样追踪 https://worldtimeapi.org/api/timezone/America/New_York

### 统一 Prompt

```
Implement a page change tracker:

1. Fetch https://httpbin.org/uuid three times with 5-second intervals
2. Record each response's UUID value and timestamp
3. Diff consecutive responses to show what changed
4. Generate a change tracking report with: timestamps, values, diff summary

Bonus: Also track https://worldtimeapi.org/api/timezone/America/New_York similarly (3 fetches, 5s intervals)

Save the report to {WORK_DIR}/change-tracking-report.md
Save raw data to {WORK_DIR}/change-data.json
```

### 评分 (满分 10)

- 3 次成功抓取: 2.5 分
- 正确 diff: 2.5 分
- 报告质量: 2 分
- 加分端点: 2 分
- 数据格式: 1 分
