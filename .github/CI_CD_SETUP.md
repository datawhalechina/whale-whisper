# GitHub Actions / 审查流程说明

本仓库包含两类自动化能力：

1. **PR 基础检查（必跑）**：确保后端/前端至少能成功编译/构建，作为合并门禁。
2. **Codex AI PR 审查（可选但推荐）**：每次 PR 自动生成一份高信噪比的代码审查意见并评论到 PR。

---

## ✅ 工作流一览

### 1) `PR Checks`（`.github/workflows/pr-check.yml`）

- **触发**：向 `main` 或 `dev` 提交 PR 时（opened/synchronize/reopened/ready_for_review）
- **内容**：
  - 后端：Python 语法编译检查（`compileall`）
  - 前端：pnpm workspace 安装依赖并构建 Web（`@whalewhisper/web build`）
- **用途**：作为合并前质量门禁（建议在分支保护中设为 Required）

### 2) `Codex PR Review`（`.github/workflows/codex-pr-review.yml`）

- **触发**：每次 PR（opened/synchronize/reopened/ready_for_review）
- **内容**：调用 `openai/codex-action` 读取 PR diff + 仓库规范文档，自动产出审查报告并评论到 PR
- **安全设计**：
  - 使用 `pull_request_target` 以便对 fork PR 也能评论（否则 token 没有写权限）
  - **不 checkout PR head/merge 代码**，审查基于 GitHub API 获取的 diff（避免执行不受信任代码）
  - Codex 沙箱设置为 `read-only`

---

## 🔐 必需配置（Secrets / Variables）

在仓库 Settings → Secrets and variables → Actions 中配置：

### Secrets（必需）

- `OPENAI_API_KEY`：Codex 审查必需

### Secrets（可选）

- `OPENAI_BASE_URL`：如使用 OpenAI 兼容网关/自建网关，可填 base url（默认走 `https://api.openai.com/v1`）

### Variables（可选）

- `OPENAI_MODEL`：默认 `gpt-5.2`
- `OPENAI_EFFORT`：默认 `high`（成本/耗时更敏感可用 `medium`）

> 没配 `OPENAI_API_KEY` 时：`Codex PR Review` 会被跳过；`PR Checks` 不受影响。

---

## 🛡️ 分支保护（建议）

Settings → Branches → Add rule

### 对 `dev` 分支

- [x] Require a pull request before merging
- [x] Require status checks to pass before merging
  - 勾选：`PR Checks / backend`、`PR Checks / frontend`
- [x] Require branches to be up to date before merging（可选，但推荐）
- [ ] Require approvals（可选：建议 1）

### 对 `main` 分支

- [x] Require a pull request before merging
- [x] Require status checks to pass before merging
  - 勾选：`PR Checks / backend`、`PR Checks / frontend`
- [x] Include administrators（推荐）
- [x] Require approvals（推荐：1-2）
- [x] Require conversation resolution before merging（推荐）

---

## 🧩 开发流程（推荐）

- `feature/*` → PR → `dev`
- `dev` → PR → `main`

