# GitHub Actions / 审查流程说明

本仓库包含两类自动化能力：

1. **PR 基础检查（必跑）**：确保后端/前端至少能成功编译/构建，作为合并门禁。
2. **PR 自动化辅助（推荐）**：自动打标签、自动补全 PR 说明，减少沟通成本。
3. **AI 审查/分诊（可选但推荐）**：PR 自动审查、Issue 自动分诊与回复（可用 Codex / Claude）。

---

## ✅ 工作流一览

> 说明：本仓库有多条工作流使用 `pull_request_target`（PR Labels、Codex/Claude PR Review、Codex PR Description）。
> GitHub 在 **2025-12-08** 起调整行为：`pull_request_target` 会始终从仓库的 **Default branch** 读取/执行 workflow。
> 因此要修改这些 workflow，必须把改动合进默认分支（当前是 `main`），否则 PR 上跑的仍是默认分支里的旧版本。

### 1) `PR Checks`（`.github/workflows/pr-check.yml`）

- **触发**：向 `main` 或 `dev` 提交 PR 时（opened/synchronize/reopened/ready_for_review）
- **内容**：
  - 后端：安装依赖 + 编译检查 + import smoke test
  - 前端：pnpm workspace 安装依赖并构建 Web（`@whalewhisper/web build`）
- **用途**：作为合并前质量门禁（建议在分支保护中设为 Required）

> 说明：如仓库里暂时没有 `backend/` 或 `frontend/`，对应 job 会输出 “skip” 提示并正常通过（便于把本仓库当作工作流测试仓库使用）。

### 2) `Test Suite`（`.github/workflows/test.yml`）

- **触发**：push 到 `main/dev`（以及手动触发）
- **内容**：与 `PR Checks` 类似，用于保证合并后的分支依然可构建

### 3) `PR Labels`（`.github/workflows/pr-label.yml`）

- **触发**：每次 PR（opened/synchronize/reopened/ready_for_review）
- **功能**：
  - 自动打 `size/*`、`area/*`、`type/*` 等标签（并确保标签存在）
  - 大 PR 会自动加 `needs-review`

### 4) `Codex PR Description`（`.github/workflows/codex-pr-description.yml`）

- **触发**：每次 PR（opened/synchronize/reopened/ready_for_review）
- **功能**：在 PR 描述中 upsert 一段 “AI 自动生成的说明”（带 marker，不覆盖你原本内容）
- **说明**：需要配置 `OPENAI_API_KEY`

### 5) `Codex PR Review`（`.github/workflows/codex-pr-review.yml`）

- **触发**：每次 PR（opened/synchronize/reopened/ready_for_review）
- **内容**：调用 `openai/codex-action` 读取 PR diff + 仓库规范文档，自动产出审查报告并评论到 PR
- **安全设计**：
  - 使用 `pull_request_target` 以便对 fork PR 也能评论（否则 token 没有写权限）
  - **不 checkout PR head/merge 代码**，审查基于 GitHub API 获取的 diff（避免执行不受信任代码）
  - Codex 沙箱设置为 `read-only`

### 6) `Claude PR Review`（`.github/workflows/claude-pr-review.yml`）

- **触发**：每次 PR（opened/synchronize/reopened/ready_for_review）
- **功能**：调用 Claude 对 PR 进行自动审查并评论到 PR
- **说明**：需要配置 `ANTHROPIC_API_KEY`（可选 `ANTHROPIC_BASE_URL`）

### 7) `Codex Issue Triage`（`.github/workflows/codex-issue-triage.yml`）

- **触发**：新建 Issue
- **功能**：自动建议/添加标签，并用固定 marker upsert 一条“首评回复”（引导补充复现信息）
- **说明**：需要配置 `OPENAI_API_KEY`

### 8) `Claude Issue Auto Response (Fallback)`（`.github/workflows/claude-issue-auto-response.yml`）

- **触发**：新建 Issue
- **功能**：当 Codex 没跑/未配置时，用 Claude 自动给出首评回复（并可补标签）
- **说明**：需要配置 `ANTHROPIC_API_KEY`

### 9) `Claude Issue Duplicate Check`（`.github/workflows/claude-issue-duplicate-check.yml`）

- **触发**：新建 Issue
- **功能**：保守地检测重复 Issue（>= 85% 才行动），自动加 `duplicate` 标签并留言指向原 Issue
- **说明**：需要配置 `ANTHROPIC_API_KEY`

### 10) `Stale Cleanup`（`.github/workflows/issue-stale.yml`）

- **触发**：每天定时 + 手动触发
- **功能**：对长期无更新的 Issue/PR 标记 `status/stale`；Issue 进一步自动关闭

### 11) `Release`（`.github/workflows/release.yml`）

- **触发**：push tag（`v*`）
- **功能**：自动创建 GitHub Release（使用 GitHub 自动生成的 Release Notes）

---

## 🔐 必需配置（Secrets / Variables）

在仓库 Settings → Secrets and variables → Actions 中配置：

### Secrets（必需）

- `OPENAI_API_KEY`：Codex 审查/PR说明/Issue分诊必需
- `ANTHROPIC_API_KEY`：Claude PR 审查/Issue 自动回复/重复检测必需

### Secrets（可选）

- `OPENAI_BASE_URL`：如使用 OpenAI 兼容网关/自建网关，可填网关地址（推荐填到 `/v1` 或完整的 `/v1/responses`；workflow 会自动补全 `/responses`）。不填则使用 `openai/codex-action` 内置默认端点。
- `ANTHROPIC_BASE_URL`：如使用 Anthropic 兼容网关/自建网关，可填 base url

### Variables（可选）

- `OPENAI_MODEL`：默认 `gpt-5.2`
- `OPENAI_EFFORT`：默认 `high`（成本/耗时更敏感可用 `medium`）

> 没配 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` 时：对应 AI 工作流会直接失败（用于把 AI 检查设为 Required 时“没配 key 就挡住合并”）。

### Actions 设置（必需）

Settings → Actions → General → Workflow permissions：

- 选择 **Read and write permissions**（否则自动打标签/写 PR 描述/评论会 403）

---

## 🛡️ 分支保护（建议）

Settings → Branches → Add rule

### 对 `dev` 分支

- [x] Require a pull request before merging
- [x] Require status checks to pass before merging
  - 勾选：`PR Checks / backend`、`PR Checks / frontend`
  - 如要把 AI 也设为门禁，再勾选：`Codex PR Review / pr-review`、`Claude PR Review / pr-review`
  - （可选）如希望 PR 描述也必须自动生成，再勾选：`Codex PR Description / pr-description`
- [x] Require branches to be up to date before merging（可选，但推荐）
- [ ] Require approvals（可选：建议 1）

### 对 `main` 分支

- [x] Require a pull request before merging
- [x] Require status checks to pass before merging
  - 勾选：`PR Checks / backend`、`PR Checks / frontend`
  - 如要把 AI 也设为门禁，再勾选：`Codex PR Review / pr-review`、`Claude PR Review / pr-review`
  - （可选）如希望 PR 描述也必须自动生成，再勾选：`Codex PR Description / pr-description`
- [x] Include administrators（推荐）
- [x] Require approvals（推荐：1-2）
- [x] Require conversation resolution before merging（推荐）

> 如果在 ruleset 里搜不到某个 check 名称：先创建一个 PR 让对应 workflow 跑一次，再回来 Add checks。

---

## 🧩 开发流程（推荐）

- `feature/*` → PR → `dev`
- `dev` → PR → `main`
