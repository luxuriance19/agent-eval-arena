# Category 2: 浏览器操作

## Task 2A: 表单填写 (权重 28%)

### 目标

在 https://demoqa.com/automation-practice-form 填写学生注册表单。

### 步骤

1. 导航到表单页面
2. 填写以下字段:
   - First Name: Alice
   - Last Name: Zhang
   - Email: alice.zhang@example.com
   - Gender: Female (单选)
   - Mobile: 1234567890
   - Subjects: Computer Science
   - Hobbies: Sports, Reading (多选)
   - Current Address: 123 Test Street, San Francisco, CA 94102
3. 点击 Submit
4. 截图确认弹窗
5. 从弹窗提取提交的数据

### 统一 Prompt

```
Use browser automation to navigate to https://demoqa.com/automation-practice-form and complete the student registration form with these values:
- First Name: Alice
- Last Name: Zhang
- Email: alice.zhang@example.com
- Gender: Female
- Mobile: 1234567890
- Subjects: Computer Science
- Hobbies: Sports, Reading
- Current Address: 123 Test Street, San Francisco, CA 94102

Submit the form, take a screenshot of the confirmation modal, and extract all submitted data from the modal. Save the screenshot to {WORK_DIR}/form-result.png and the extracted data to {WORK_DIR}/form-data.json.
```

### 评分 (满分 10)

- 每个正确填写的字段: 0.8 分 (9 字段 × 0.8 = 7.2)
- 截图捕获: 1.0 分
- 数据提取: 1.8 分

---

## Task 2B: 数据提取 (权重 28%)

### 目标

从 Hacker News 提取 Top 15 故事。

### 步骤

1. 导航到 https://news.ycombinator.com
2. 提取 Top 15 故事: rank, title, URL, points, author, comment_count
3. 输出为 JSON 数组
4. 找出得分最高的故事
5. 截图

### 统一 Prompt

```
Navigate to https://news.ycombinator.com using browser automation. Extract the top 15 stories with these fields for each: rank, title, url, points, author, comment_count. Output as a JSON array to {WORK_DIR}/hn-stories.json. Identify which story has the most points. Take a screenshot and save to {WORK_DIR}/hn-screenshot.png.
```

### 评分 (满分 10)

- 15 条故事正确提取: 3 分
- 每条故事字段完整: 3 分
- JSON 有效: 1.5 分
- 最高分识别: 1.5 分
- 截图: 1 分

---

## Task 2C: 多步导航 (权重 24%)

### 目标

在 GitHub Trending 页面进行多步导航和数据提取。

### 步骤

1. 导航到 https://github.com/trending
2. 提取 Top 5 trending 仓库 (name, description, language, stars_today)
3. 点击第一个仓库链接
4. 在仓库页面提取: README 第一段、stars、forks、最新 commit message
5. 返回 trending 页面
6. 切换到 "This week" 过滤器
7. 提取 Top 3 仓库
8. 在步骤 2、4、6 处各截一张图

### 统一 Prompt

```
Perform a multi-step browser navigation task:

1. Go to https://github.com/trending
2. Extract top 5 trending repos (name, description, language, stars_today). Save to {WORK_DIR}/trending-daily.json. Screenshot as {WORK_DIR}/step1.png
3. Click the first repository link
4. On the repo page, extract: README first paragraph, total stars, total forks, latest commit message. Save to {WORK_DIR}/repo-detail.json. Screenshot as {WORK_DIR}/step2.png
5. Navigate back to trending page
6. Switch to "This week" time filter
7. Extract top 3 repos. Save to {WORK_DIR}/trending-weekly.json. Screenshot as {WORK_DIR}/step3.png
```

### 评分 (满分 10)

- 每个成功步骤: 1 分 (7 步 × 1 = 7)
- 三张截图: 1.5 分
- 数据准确性: 1.5 分

---

## Task 2D: 截图+内容总结 (权重 20%)

### 目标

从 OpenAI Blog 提取内容并总结。

### 步骤

1. 导航到 https://openai.com/blog
2. 全页截图
3. 提取最新 5 篇博客标题和日期
4. 进入最新一篇
5. 提取全文
6. 生成 3 句话摘要
7. 截图该文章

### 统一 Prompt

```
Navigate to https://openai.com/blog using browser automation:

1. Take a full-page screenshot, save as {WORK_DIR}/blog-overview.png
2. Extract the 5 most recent blog post titles and dates, save to {WORK_DIR}/blog-posts.json
3. Click into the most recent post
4. Extract the full text content, save to {WORK_DIR}/latest-post.txt
5. Generate a 3-sentence summary of the post, save to {WORK_DIR}/summary.txt
6. Take a screenshot of the post, save as {WORK_DIR}/latest-post.png
```

### 评分 (满分 10)

- 全页截图: 1.5 分
- 5 篇标题+日期: 2 分
- 全文提取: 2 分
- 摘要质量: 2.5 分
- 文章截图: 1 分
- JSON 格式正确: 1 分
