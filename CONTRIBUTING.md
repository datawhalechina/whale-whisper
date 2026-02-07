# 🤝 贡献指南 | CONTRIBUTING

> 🇺🇸 English version is provided after the Chinese section. Scroll to [English Contributing Guide](#english-contributing-guide) for the translation.

## 🔁 语言导航 | Language Navigation

- 🇨🇳 [中文贡献指南](#中文贡献指南)
- 🇺🇸 [English Contributing Guide](#english-contributing-guide)

---

## 🇨🇳 中文贡献指南

### 📚 中文目录

- [1. 介绍](#1-介绍)
- [2. 行为准则](#2-行为准则)
- [3. 快速开始](#3-快速开始)
- [4. 如何贡献](#4-如何贡献)
- [5. 分支命名](#5-分支命名)
- [6. 提交格式](#6-提交格式)
- [7. 代码风格](#7-代码风格)
- [8. 测试](#8-测试)
- [9. PR 流程](#9-pr-流程)
- [10. 问题反馈](#10-问题反馈)

### 1. 介绍

WhaleWhisper（鲸语）是一个模块化的数字人/虚拟角色智能体框架，提供完整的数字人解决方案。本文档说明如何为项目贡献高质量的代码和文档。

**核心能力：**
- 角色舞台：Live2D/VRM 模型渲染与智能表情动作
- 多模态交互：文本对话 + ASR + TTS
- 智能体编排：LLM 推理 + Agent 工作流
- 本地记忆：SQLite 对话记忆管理
- 多端支持：Web + Tauri 桌面端

### 2. 行为准则

- 以尊重、同理心和耐心进行交流，遵循 Contributor Covenant 2.1 精神
- 严禁骚扰、歧视或人身攻击
- 基于事实和数据进行讨论，清晰记录技术权衡
- 主要沟通渠道：GitHub Issues/Discussions 和 README.md 中列出的社区群组
- 期望在两个工作日内得到回复

### 3. 快速开始

#### 克隆仓库并安装依赖

```bash
git clone https://github.com/datawhalechina/WhaleWhisper.git
cd WhaleWhisper
```

#### 后端设置

```bash
cd backend

# 方式一：使用 uv（推荐）
uv venv
uv pip install -e ".[dev]"

# 方式二：使用传统 venv
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -e ".[dev]"
```

#### 前端设置

```bash
cd frontend
pnpm install
```

#### 配置环境

编辑 `backend/config/engines.yaml` 配置 LLM/ASR/TTS 提供商：

```yaml
llm:
  default: openai
  providers:
    openai:
      api_key: "your-api-key"
      model: "gpt-4"
```

#### 启动开发服务器

```bash
# 后端（在 backend/ 目录）
uvicorn app.main:app --reload --port 8090

# 前端（在 frontend/ 目录）
pnpm --filter @whalewhisper/web dev
```

访问 http://localhost:5173 查看应用。

### 4. 如何贡献

> ⚠️ 重要：所有 PR 必须提交到 `dev` 分支
> 📌 注意：`main` 分支仅用于发布，不要直接推送或合并到 main

#### 贡献流程

1. **同步最新代码**

   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   ```

2. **保持改动聚焦**
   - 每个 PR 只解决一个问题或添加一个功能
   - 在提交信息或 PR 描述中说明改动原因

3. **运行测试**
   - 提交前运行 [测试](#8-测试) 中列出的检查命令

4. **推送并创建 PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   - 在 GitHub 上创建 PR，目标分支选择 `dev`

### 5. 分支命名

遵循以下命名规范：

| 分支类型 | 命名格式 | 说明 |
|---------|---------|------|
| `feature/<描述>` | `feature/live2d-emotion` | 新功能或 UI 改进 |
| `fix/<问题ID或范围>` | `fix/websocket-reconnect` | Bug 修复 |
| `hotfix/<范围>` | `hotfix/memory-leak` | 紧急生产修复（通过 PR 合并到 dev） |
| `chore/<范围>` | `chore/update-deps` | 文档、工具、依赖更新 |

### 6. 提交格式

遵循 Conventional Commits 规范，使用简洁的英文描述：

| 类型 | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能或增强 | `feat: add VRM model support` |
| `fix` | Bug 修复 | `fix: resolve WebSocket reconnection issue` |
| `chore` | 工具、文档、维护 | `chore: update FastAPI to 0.110` |
| `refactor` | 内部重构（不改变行为） | `refactor: simplify memory storage logic` |
| `test` | 添加或调整测试 | `test: add unit tests for ASR module` |
| `docs` | 文档更新 | `docs: update installation guide` |

**提交示例：**
```bash
git commit -m "feat: add emotion detection for Live2D models"
git commit -m "fix: handle TTS timeout gracefully"
```

### 7. 代码风格

#### 后端（Python）

- 遵循 PEP 8 规范
- 使用 4 空格缩进
- 类型注解：优先使用 Python 3.8+ 类型提示
- 异步优先：FastAPI 路由使用 `async def`
- 配置驱动：使用 YAML 配置文件而非硬编码

**示例：**
```python
from typing import Optional
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

#### 前端（TypeScript/Vue）

- 使用 2 空格缩进
- 优先使用 TypeScript 严格模式
- Vue 3 Composition API（`<script setup>`）
- 组件命名：PascalCase（如 `CharacterStage.vue`）
- 工具函数：放在 `frontend/packages/shared` 或相应模块的 `utils/` 目录

**示例：**
```vue
<script setup lang="ts">
import { ref } from 'vue'

const message = ref<string>('Hello')
</script>

<template>
  <div>{{ message }}</div>
</template>
```

#### 通用规范

- 保持函数单一职责
- 复用 `backend/app/` 和 `frontend/packages/` 中的工具函数
- 避免过度工程化，只添加必要的抽象

### 8. 测试

提交 PR 前，请在本地运行以下检查：

#### 后端测试

```bash
cd backend

# Python 语法检查
python -m compileall -q app

# 导入测试
python -c "from app.main import app; print('backend import: ok')"

# 运行单元测试（如果有）
# Run unit tests (if available; tests directory not yet created)
```

#### 前端测试

```bash
cd frontend

# 类型检查
pnpm run typecheck

# 构建测试
pnpm --filter @whalewhisper/web build
```

#### 集成测试

- 启动后端和前端，验证核心功能正常工作
- 测试 WebSocket 连接、对话流程、表情动作触发

### 9. PR 流程

> ⚠️ 重要：PR 基础分支设置为 `dev`，确保 CI 通过后再合并
> 📌 注意：如果分支落后，请 rebase 到 `origin/dev`

#### PR 提交清单

1. **填写 PR 模板**
   - 提供上下文说明、截图/日志、测试说明

2. **确认检查项**
   - [ ] 基础分支是 `dev`
   - [ ] 所有必需的 CI 检查通过（backend、frontend）
   - [ ] 已解决冲突，分支是最新的
   - [ ] 关联相关 Issues 或 Discussions

3. **等待审查**
   - 维护者将在两个工作日内回复
   - 如需修改，继续推送到同一分支即可

4. **合并策略**
   - 使用 "Squash and merge" 保持提交历史整洁

#### PR 示例标题

- `feat: add Live2D emotion auto-trigger`
- `fix: resolve memory leak in WebSocket handler`
- `chore: update dependencies and CI workflows`

### 10. 问题反馈

#### 提交 Issue

在 [Issues](https://github.com/datawhalechina/WhaleWhisper/issues) 中提交问题时，请包含：

1. **清晰的标题**：简洁描述问题
2. **标签**：选择合适的标签（bug、enhancement、question 等）
3. **复现步骤**：详细说明如何触发问题
4. **期望行为 vs 实际行为**：说明预期结果和实际结果
5. **日志和截图**：提供错误日志、控制台输出或截图
6. **环境信息**：
   - 操作系统（Windows/Linux/Mac）
   - Python 版本
   - Node.js 版本
   - 浏览器版本（如适用）

#### Issue 模板示例

```markdown
### 问题描述
WebSocket 连接在 5 分钟后自动断开

### 复现步骤
1. 启动后端和前端
2. 打开浏览器访问 http://localhost:5173
3. 等待 5 分钟
4. 观察到 WebSocket 断开

### 期望行为
WebSocket 应保持长连接

### 实际行为
5 分钟后自动断开，控制台显示 "Connection closed"

### 环境信息
- OS: Windows 11
- Python: 3.11.5
- Node.js: 20.10.0
- Browser: Chrome 120

### 日志
```
[ERROR] WebSocket connection timeout
```
```

#### 功能建议

如果你有功能建议，请在 Issue 中说明：
- 功能描述和使用场景
- 为什么这个功能有价值
- 可能的实现方案（可选）

---

## 🇺🇸 English Contributing Guide

### 📚 Table of Contents

- [1. Introduction](#1-introduction)
- [2. Code of Conduct](#2-code-of-conduct)
- [3. Getting Started](#3-getting-started)
- [4. How to Contribute](#4-how-to-contribute)
- [5. Branch Naming](#5-branch-naming)
- [6. Commit Format](#6-commit-format)
- [7. Code Style](#7-code-style)
- [8. Testing](#8-testing)
- [9. PR Process](#9-pr-process)
- [10. Issue Reporting](#10-issue-reporting)

### 1. Introduction

WhaleWhisper is a modular digital human/virtual character agent framework providing complete digital human solutions. This document explains how to contribute high-quality code and documentation to the project.

**Core Capabilities:**
- Character Stage: Live2D/VRM model rendering with intelligent emotion/action control
- Multimodal Interaction: Text chat + ASR + TTS
- Agent Orchestration: LLM inference + Agent workflows
- Local Memory: SQLite-based conversation memory management
- Multi-platform: Web + Tauri desktop

### 2. Code of Conduct

- Communicate with respect, empathy, and patience—follow the spirit of Contributor Covenant 2.1
- Absolutely no harassment, discrimination, or personal attacks
- Base discussions on facts and data; document trade-offs clearly
- Primary channels: GitHub Issues/Discussions and community groups listed in README.md
- Expect responses within two business days

### 3. Getting Started

#### Clone and Install Dependencies

```bash
git clone https://github.com/datawhalechina/WhaleWhisper.git
cd WhaleWhisper
```

#### Backend Setup

```bash
cd backend

# Option 1: Using uv (recommended)
uv venv
uv pip install -e ".[dev]"

# Option 2: Using traditional venv
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -e ".[dev]"
```

#### Frontend Setup

```bash
cd frontend
pnpm install
```

#### Configure Environment

Edit `backend/config/engines.yaml` to configure LLM/ASR/TTS providers:

```yaml
llm:
  default: openai
  providers:
    openai:
      api_key: "your-api-key"
      model: "gpt-4"
```

#### Launch Dev Servers

```bash
# Backend (in backend/ directory)
uvicorn app.main:app --reload --port 8090

# Frontend (in frontend/ directory)
pnpm --filter @whalewhisper/web dev
```

Visit http://localhost:5173 to view the application.

### 4. How to Contribute

> ⚠️ Important: Every PR must target the `dev` branch
> 📌 Notice: `main` is release-only; never push or merge into it directly

#### Contribution Workflow

1. **Sync Latest Code**

   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   ```

2. **Keep Changes Focused**
   - Each PR should solve one problem or add one feature
   - Document reasoning in commit messages or PR descriptions

3. **Run Tests**
   - Run checks listed in [Testing](#8-testing) before pushing

4. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   - Create PR on GitHub targeting `dev` branch

### 5. Branch Naming

Follow these naming conventions:

| Branch Type | Format | Description |
|------------|--------|-------------|
| `feature/<description>` | `feature/live2d-emotion` | New features or UI improvements |
| `fix/<issue-id-or-scope>` | `fix/websocket-reconnect` | Bug fixes |
| `hotfix/<scope>` | `hotfix/memory-leak` | Urgent production fixes (merge to dev via PR) |
| `chore/<scope>` | `chore/update-deps` | Docs, tooling, dependency updates |

### 6. Commit Format

Follow Conventional Commits with concise English descriptions:

| Type | Purpose | Example |
|------|---------|---------|
| `feat` | New feature or enhancement | `feat: add VRM model support` |
| `fix` | Bug fix | `fix: resolve WebSocket reconnection issue` |
| `chore` | Tooling, docs, maintenance | `chore: update FastAPI to 0.110` |
| `refactor` | Internal refactor (no behavior change) | `refactor: simplify memory storage logic` |
| `test` | Add or adjust tests | `test: add unit tests for ASR module` |
| `docs` | Documentation updates | `docs: update installation guide` |

**Commit Examples:**
```bash
git commit -m "feat: add emotion detection for Live2D models"
git commit -m "fix: handle TTS timeout gracefully"
```

### 7. Code Style

#### Backend (Python)

- Follow PEP 8 guidelines
- Use 4-space indentation
- Type annotations: prefer Python 3.8+ type hints
- Async-first: use `async def` for FastAPI routes
- Configuration-driven: use YAML config files instead of hardcoding

**Example:**
```python
from typing import Optional
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

#### Frontend (TypeScript/Vue)

- Use 2-space indentation
- Prefer TypeScript strict mode
- Vue 3 Composition API (`<script setup>`)
- Component naming: PascalCase (e.g., `CharacterStage.vue`)
- Utility functions: place in `frontend/packages/shared` or module-specific `utils/` directories

**Example:**
```vue
<script setup lang="ts">
import { ref } from 'vue'

const message = ref<string>('Hello')
</script>

<template>
  <div>{{ message }}</div>
</template>
```

#### General Guidelines

- Keep functions single-purpose
- Reuse utilities from `backend/app/` and `frontend/packages/`
- Avoid over-engineering; only add necessary abstractions

### 8. Testing

Before submitting a PR, run these checks locally:

#### Backend Tests

```bash
cd backend

# Python syntax check
python -m compileall -q app

# Import test
python -c "from app.main import app; print('backend import: ok')"

# Run unit tests (if available)
# Run unit tests (if available; tests directory not yet created)
```

#### Frontend Tests

```bash
cd frontend

# Type check
pnpm run typecheck

# Build test
pnpm --filter @whalewhisper/web build
```

#### Integration Tests

- Start backend and frontend, verify core functionality works
- Test WebSocket connection, conversation flow, emotion/action triggers

### 9. PR Process

> ⚠️ Important: Set PR base to `dev`, ensure CI is green before merging
> 📌 Notice: Rebase onto `origin/dev` if branch falls behind

#### PR Submission Checklist

1. **Fill Out PR Template**
   - Provide context, screenshots/logs, testing notes

2. **Confirm Checklist**
   - [ ] Base branch is `dev`
   - [ ] All required CI checks pass (backend, frontend)
   - [ ] Conflicts resolved and branch up to date
   - [ ] Linked related Issues or Discussions

3. **Wait for Review**
   - Maintainers will respond within two business days
   - Continue pushing to the same branch for follow-up changes

4. **Merge Strategy**
   - Use "Squash and merge" to keep history tidy

#### PR Title Examples

- `feat: add Live2D emotion auto-trigger`
- `fix: resolve memory leak in WebSocket handler`
- `chore: update dependencies and CI workflows`

### 10. Issue Reporting

#### Submitting Issues

When filing [Issues](https://github.com/datawhalechina/WhaleWhisper/issues), include:

1. **Clear Title**: Concise problem description
2. **Labels**: Choose appropriate labels (bug, enhancement, question, etc.)
3. **Reproduction Steps**: Detailed steps to trigger the issue
4. **Expected vs Actual Behavior**: Describe expected and actual results
5. **Logs and Screenshots**: Provide error logs, console output, or screenshots
6. **Environment Info**:
   - Operating System (Windows/Linux/Mac)
   - Python version
   - Node.js version
   - Browser version (if applicable)

#### Issue Template Example

```markdown
### Problem Description
WebSocket connection automatically disconnects after 5 minutes

### Reproduction Steps
1. Start backend and frontend
2. Open browser at http://localhost:5173
3. Wait 5 minutes
4. Observe WebSocket disconnect

### Expected Behavior
WebSocket should maintain long connection

### Actual Behavior
Disconnects after 5 minutes, console shows "Connection closed"

### Environment Info
- OS: Windows 11
- Python: 3.11.5
- Node.js: 20.10.0
- Browser: Chrome 120

### Logs
```
[ERROR] WebSocket connection timeout
```
```

#### Feature Requests

For feature suggestions, include in the Issue:
- Feature description and use cases
- Why this feature adds value
- Possible implementation approaches (optional)

---

## 🙏 Acknowledgments

Thank you for contributing to WhaleWhisper! Your efforts help make this project better for everyone.

If you have questions or need help, feel free to:
- Open a [Discussion](https://github.com/datawhalechina/WhaleWhisper/discussions)
- Contact the [Datawhale team](https://github.com/datawhalechina/DOPMC/blob/main/OP.md)
- Join our community groups listed in README.md

Happy coding! 🐋✨
