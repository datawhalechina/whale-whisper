# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

WhaleWhisper（鲸语）是一个模块化的数字人/虚拟角色智能体框架，提供完整的数字人解决方案。核心能力包括：

- **角色舞台**：支持 Live2D/VRM 模型渲染，可根据对话内容自动调用表情和动作
- **多模态交互**：文本对话 + 语音识别(ASR) + 语音合成(TTS)
- **智能体编排**：LLM 推理 + Agent 工作流 + 工具调用
- **本地记忆**：基于 SQLite 的对话记忆与上下文管理
- **多端支持**：Web 应用 + Tauri 桌面端

## 开发环境要求

- Python 3.10+（CI: 3.11）
- Node.js 20+
- pnpm 9.12.2
- uv（推荐用于 Python 依赖管理）

## 快速开始

### 1. 启动后端

```bash
cd backend

# 方式一：使用 uv（推荐）
uv venv
uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload --port 8090

# 方式二：使用传统 venv
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8090
```

后端服务地址：
- 健康检查：http://localhost:8090/health
- WebSocket：ws://localhost:8090/ws
- API 端点：`/api/llm`、`/api/asr`、`/api/tts`、`/api/agent`、`/api/memory`、`/api/providers`

### 2. 启动前端

```bash
cd frontend
pnpm install
pnpm --filter @whalewhisper/web dev
```

访问 http://localhost:5174

## 项目结构

```
WhaleWhisper/
├── backend/          # FastAPI 后端服务
│   ├── app/         # 应用核心代码
│   │   ├── api/     # API 路由（llm.py, asr.py, tts.py, agent.py, memory.py 等）
│   │   ├── core/    # 核心模块（engines, agents, memory, providers）
│   │   ├── services/# 业务服务
│   │   ├── extensions/# 扩展模块
│   │   └── main.py  # 应用入口
│   ├── config/      # 配置文件（engines.yaml 等）
│   ├── examples/    # 示例代码
│   └── scripts/     # 脚本
├── frontend/         # 前端工作区（pnpm workspace）
│   ├── apps/
│   │   ├── web/            # Web 应用
│   │   └── desktop-tauri/  # Tauri 桌面应用
│   └── packages/           # 共享组件库
├── airi/            # 数字人交互框架（子模块）
├── assets/          # 静态资源（模型、素材）
├── data/            # 数据/缓存
└── scripts/         # 构建与部署脚本
```

## 核心架构

### 配置驱动架构

项目采用 YAML 配置驱动，主要配置文件位于 `backend/config/`：

- `engines.yaml` - LLM/ASR/TTS/Agent 引擎配置，支持多提供商（OpenAI、Groq、DeepSeek、Dify、Coze 等）
- `plugins.yaml` - 插件配置
- `providers.yaml` - 提供商配置

配置结构示例：
```yaml
llm:
  default: openai
  engines:
    - id: openai
      type: openai_compat
      base_url: https://api.openai.com/v1
      model: gpt-4o-mini
      api_key_env: OPENAI_API_KEY
```

### 异步优先

- FastAPI 路由全部使用 `async def`
- 数据库操作、API 调用等 I/O 密集型任务使用异步
- 避免阻塞事件循环

### 模块化设计

- **引擎层**：抽象不同 AI 服务商的统一接口（OpenAI 兼容、Dify、Coze 等）
- **服务层**：业务逻辑封装（LLM、ASR、TTS、Agent、Memory）
- **API 层**：HTTP/WebSocket 接口
- **扩展层**：插件系统、事件分发

## 代码规范

### 后端（Python）

- 遵循 PEP 8 规范
- 使用 4 空格缩进
- 类型注解：Python 3.10+ 类型提示
- 异步优先：`async def`
- 配置驱动：避免硬编码

示例：
```python
from typing import Optional
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

### 前端（TypeScript/Vue）

- 2 空格缩进
- TypeScript 严格模式
- Vue 3 Composition API（`<script setup>`）
- 组件命名：PascalCase
- 共享代码放在 `frontend/packages/`，应用内代码放在对应 `frontend/apps/*/src`

示例：
```vue
<script setup lang="ts">
import { ref } from 'vue'

const message = ref<string>('Hello')
</script>

<template>
  <div>{{ message }}</div>
</template>
```

### Git 工作流

- **分支规范**：
  - `feature/<描述>` - 新功能（如 `feature/live2d-emotion`）
  - `fix/<问题ID或范围>` - Bug 修复（如 `fix/websocket-reconnect`）
  - `hotfix/<范围>` - 紧急修复
  - `chore/<范围>` - 文档、工具、依赖更新

- **提交格式**：Conventional Commits
  ```
  feat: add VRM model support
  fix: resolve WebSocket reconnection issue
  chore: update FastAPI to 0.110
  ```

- **PR 流程**：
  - 所有 PR 必须提交到 `dev` 分支（`main` 仅用于发布）
  - 使用 "Squash and merge" 保持提交历史整洁
  - PR 标题遵循提交格式规范

## 测试

提交 PR 前，请在本地运行以下检查：

### 后端测试

```bash
cd backend

# Python 语法检查
python -m compileall -q app

# 导入测试
python -c "from app.main import app; print('backend import: ok')"
```

### 前端测试

```bash
cd frontend

# 构建测试
pnpm --filter @whalewhisper/web build
```

### 集成测试

- 启动后端和前端，验证核心功能正常工作
- 测试 WebSocket 连接、对话流程、表情动作触发

## 常用命令

### 后端

```bash
# 安装依赖
cd backend
uv pip install -e ".[dev]"

# 启动开发服务器
uv run uvicorn app.main:app --reload --port 8090

# 语法检查
python -m compileall -q app
```

### 前端

```bash
# 安装依赖
cd frontend
pnpm install

# 启动 Web 开发服务器
pnpm --filter @whalewhisper/web dev

# 构建 Web 应用
pnpm --filter @whalewhisper/web build

# 构建桌面应用
pnpm --filter @whalewhisper/desktop-tauri build
```

### 配置

编辑 `backend/config/engines.yaml` 配置 LLM/ASR/TTS 提供商：

```yaml
llm:
  default: openai
  providers:
    openai:
      api_key: "your-api-key"
      model: "gpt-4"
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ENGINE_CONFIG_PATH` | Engine 配置文件路径 | `backend/config/engines.yaml` |
| `WS_AUTH_TOKEN` | WebSocket 鉴权令牌（可选） | - |
| `DATABASE_URL` | 数据库连接字符串 | SQLite 本地文件 |

## 常见问题

### WebSocket 连接问题

- 检查后端服务是否正常运行
- 验证 WebSocket 地址是否正确：`ws://localhost:8090/ws`
- 查看浏览器控制台和网络面板排查问题

### 模型加载问题

- 检查模型文件路径配置
- 验证模型格式是否支持（Live2D/VRM）
- 查看后端日志获取详细错误信息

### API 密钥配置

- 在 `backend/config/engines.yaml` 中配置
- 或使用环境变量（推荐）
- 确保密钥有效且未过期

## 贡献指南

1. 阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细规范
2. 所有 PR 必须提交到 `dev` 分支
3. 遵循代码风格和提交格式规范
4. 提交前运行测试和构建检查
5. 保持 PR 聚焦，避免混合多个功能

## 相关资源

- [项目 README](README.md)
- [贡献指南](CONTRIBUTING.md)
- [airi 框架](airi/) - 数字人交互框架子模块
