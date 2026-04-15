# Category 4: 真实交互

## Task 4A: GitHub Discussions 发帖 (权重 32%)

### 目标

在 GitHub 仓库创建一篇结构化的 Discussion。

### 步骤

1. 确认仓库 `luxuriance19/agent-eval-arena` 存在（不存在则创建）
2. 在仓库上启用 GitHub Discussions（如未启用）
3. 在 "General" 分类创建 Discussion:
   - 标题: "AI Coding Agent Evaluation Framework - Design Discussion"
   - 正文: 300-500 字结构化内容
     - 为什么对比 coding agents 很重要
     - 4 个评估维度的介绍
     - 邀请社区参与评估方法论讨论
     - 使用 Markdown 格式: 标题、列表、代码块
4. 验证创建成功
5. 返回 Discussion URL

### 统一 Prompt

```
Using the gh CLI (authenticated as luxuriance19):

1. Ensure the repository luxuriance19/agent-eval-arena exists. If not, create it as a public repo with a README.
2. Enable GitHub Discussions on the repo if not already enabled.
3. Create a Discussion in the "General" category:
   - Title: "AI Coding Agent Evaluation Framework - Design Discussion"
   - Body: A well-structured post (300-500 words) covering:
     - Why comparing AI coding agents matters for developer productivity
     - The 4 evaluation dimensions: code quality, browser automation, web monitoring, real-world interaction
     - How we're using Claude Sonnet as a consistent baseline model
     - An invitation for community input on evaluation methodology
   - Use proper Markdown: ## headers, bullet lists, `code` spans, **bold** for emphasis
4. Verify the discussion was created successfully
5. Report the discussion URL

Save the discussion URL and body to {WORK_DIR}/discussion-result.json
```

### 评分 (满分 10)

- 仓库确认/创建: 1 分
- Discussions 启用: 1 分
- 帖子创建成功: 2 分
- 内容质量 (300-500 字, 结构化): 3 分
- Markdown 格式: 1.5 分
- 验证 + URL 返回: 1.5 分

---

## Task 4B: Dev.to 草稿 (权重 32%)

### 目标

在 Dev.to 上创建一篇技术文章草稿。

### 方法

优先使用 Dev.to API (需要 `DEV_TO_API_KEY` 环境变量)。
如果没有 API Key，使用浏览器自动化登录创建。

### 统一 Prompt

```
Create a draft post on Dev.to about comparing AI coding agents:

Method: Use the Dev.to API if DEV_TO_API_KEY is available in the environment. Otherwise, use browser automation to log in and create the post.

Post details:
- Title: "Comparing AI Coding Agents: Claude Code vs OpenClaw vs Hermes Agent"
- Tags: ai, coding, tools, comparison
- Body (500-800 words) covering:
  - Introduction: The rise of AI coding agents and why systematic comparison matters
  - Three Agents Overview: Brief description of Claude Code (Anthropic's CLI agent), OpenClaw (open-source multi-channel assistant), and Hermes Agent (self-improving agent with learning loop)
  - Evaluation Methodology: 4 categories × 25% weight, 5 scoring dimensions, consistent baseline model
  - Key Observations: Different architectural philosophies (coding-first vs gateway-first vs learning-first)
  - Conclusion: Call to action for the community to contribute evaluation tasks
- Use Markdown formatting: headers, code blocks, bold/italic, links
- IMPORTANT: Save as DRAFT only. Do NOT publish.

Save the draft URL or confirmation to {WORK_DIR}/devto-result.json
Save the post body to {WORK_DIR}/devto-draft.md
```

### 评分 (满分 10)

- 草稿创建成功: 2.5 分
- 内容质量 (500-800 字): 3 分
- Markdown 格式: 2 分
- Tags 和元数据: 1.5 分
- 确认信息: 1 分

---

## Task 4C: 向 Trending 仓库提 PR (权重 36%)

### 目标

找到一个真实可改进的热门仓库，提交有意义的 PR。

### 步骤

1. 访问 https://github.com/trending/python?since=daily
2. 检查 3-5 个仓库，寻找真实的改进机会:
   - README 中的 typo
   - 缺少类型注解的函数
   - 缺失的测试用例
   - 不完整的 docstring
   - 小 bug 或边界情况
3. Fork 目标仓库
4. Clone fork 到本地
5. 创建 feature branch
6. 做修改并 commit
7. Push 到 fork
8. 创建 PR:
   - 清晰的标题
   - 解释修改内容和原因
   - 引用相关 issue (如有)

### 统一 Prompt

```
Find a trending Python repository on GitHub and submit a meaningful improvement PR:

1. Visit https://github.com/trending/python?since=daily
2. Examine 3-5 repositories looking for genuine improvement opportunities:
   - Typos in README or documentation
   - Missing type annotations
   - Missing or incomplete tests
   - Small bugs or edge cases
   - Incomplete docstrings
3. When you find a real improvement opportunity:
   a. Fork the repository (using gh CLI as luxuriance19)
   b. Clone the fork to {WORK_DIR}/pr-workspace/
   c. Create a descriptive branch name
   d. Make the fix with a clear commit message
   e. Push to the fork
   f. Create a Pull Request with:
      - Clear title describing the fix
      - Body explaining what was changed and why
      - Reference to relevant issue if applicable
4. Report the PR URL

IMPORTANT: The fix must be genuine and helpful. Do NOT submit trivial or spam PRs.
If no suitable improvement is found after examining 5 repos, report that finding with details of what you checked.

Save results to {WORK_DIR}/pr-result.json with: repo_name, pr_url, description, repos_examined
```

### 评分 (满分 10)

- 仓库识别 (含真实问题): 2 分
- Fork + branch 创建: 1.5 分
- 修复质量: 3 分
- PR 质量 (标题、正文、格式): 2 分
- 贡献的真实性和价值: 1.5 分

### 注意事项

- 如果确实找不到合适的改进，诚实报告比强行提交垃圾 PR 好
- 评估时会检查 PR 是否被目标仓库接受/回复
