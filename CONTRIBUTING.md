# 贡献指南

欢迎反馈问题并参与开发。本项目采用 MIT 许可证，是面向全国中小学的单校自建排课、调课与代课管理系统。

## 反馈问题

到 GitHub 开 Issue,请尽量附上:

- 复现步骤、预期行为与实际行为。
- 环境：部署方式（拉取镜像或源代码）、`IMAGE_TAG` 或提交版本、操作系统。
- 相关日志：`sudo docker compose logs --tail=100 api`（或 worker/web）。请先移除密码和 `SECRET_KEY` 等敏感信息。

## 开发环境

### 热重载全栈

```bash
cp .env.example .env
sudo docker compose -f docker-compose.dev.yml up
```

- 前端(热重载):<http://localhost:5173>
- API 互动文档:<http://localhost:5173/api/docs>

前后端源代码挂载进容器,保存文件后立即生效。前端端口由 `.env` 的 `DEV_FRONTEND_PORT` 配置；默认仅绑定 `127.0.0.1`,需从局域网访问时可将 `DEV_BIND_ADDRESS` 改为 `0.0.0.0`。API、PostgreSQL 和 Redis 不映射宿主机端口；需要命令行访问时使用 `sudo docker compose exec`。

含 `mailhog`(拦截外发邮件,Web UI <http://localhost:8025>)须以 `--profile dev` 启动，其界面端口由 `MAILHOG_UI_PORT` 配置。

### 各自本机测试

```bash
# 后端
cd backend && pip install -e ".[dev]" && pytest
# 前端
cd frontend && npm install && npm run test
```

## 程序风格与质量门槛

提交 PR 前请确保以下检查全部通过（CI 会执行同样的检查）：

| 范围 | 命令 | 要求 |
|---|---|---|
| 中文文案与术语 | `python3 scripts/check_simplified_chinese.py` | 无禁用字形、旧术语或地区化分支 |
| 后端 lint/格式 | `ruff check .` | 零错误 |
| 后端类型 | `mypy app` | 零错误 |
| 后端测试 | `pytest` | 全部通过，且不使现有测试退步 |
| 前端 lint | `npm run lint` | 零错误 |
| 前端构建+类型 | `npm run build`(含 vue-tsc) | 通过 |
| 前端单元测试 | `npm run test` | 全部通过 |

其他约定:

- **所有用户界面、接口错误、导入导出和通知文案统一使用自然简体中文。** 采用全国中小学通用教务用语，例如教学任务、作息时间表、课时、走班和班主任。冲突提示使用作息时间表中的名称（如早自习、午休、第一节），不展示内部 `period_no`。
- **数据库 schema 变更必附 Alembic 迁移**,且能从前一版顺向升级。
- solver 模块(`app/solver/`)不得 import `app.api` / `app.models`(以测试保证纯度)。
- **后台任务分两条队列**:`default` 只跑自动排课(可占住 worker 数分钟),`ops` 跑导出/备份/恢复/发送邮件与定时任务。新增后台任务时先问「这会不会跑很久」——会的话走 `default`,否则统一 `ops`,别让秒级任务排在排课后面。两者由 `worker` 与 `worker-ops` 两个容器分别监听(同一镜像,见 `app/workers/worker.py`)。
- 架构规格以 [docs/architecture.md](docs/architecture.md) 为准;与任务卡冲突时以架构文件为准并反馈矛盾。

### E2E(Playwright)

对运行中的 Docker 全栈环境驱动真实浏览器。先执行 `sudo docker compose up -d`，再创建测试账号（可重复执行），并将设置向导标记为已完成：

```bash
sudo docker compose exec -T api python -m app.scripts.seed_e2e

cd frontend
npx playwright install chromium   # 首次
npm run e2e            # 无头模式运行 E2E 回归测试（与 CI 一致）
npm run e2e:headed     # 显示浏览器并放慢执行，可在屏幕上观察
npm run e2e:perf       # 60 班压测(执行久,非回归,CI 不跑)
npm run e2e:manual     # 操作手册截图生成器(需另备示范数据测试站,CI 不跑)
```

CI 的 `e2e` 任务会在 runner 上构建三个镜像、启动全栈、创建测试账号并运行回归测试；E2E 未通过时不会发布镜像。

## 提交与 PR

- 从 `main` 开分支开发;PR 对回 `main`。
- Commit 信息用祈使句、精简描述「做了什么、为什么」。
- PR 描述请逐条对照相关任务卡的验收标准,说明验证方式与结果。
- 不 force-push 共用分支;不绕过 hook 或签名(除非明确需要)。

## 开发流程(任务卡制)

本项目以 [docs/tasks.md](docs/tasks.md) 的 Milestone 任务卡推进:一次一张卡,实现 → 依卡上「验收标准」自我验证 → 报告 → 验收后才进下一张。完成后更新该卡复选框为 `[x]` 并补「实现后」记录。临时冒出的点子记入 tasks.md 末尾的 Backlog,不顺手实现。

## 发布新版本(维护者)

镜像构建与发布已由 CI 自动化(见 [.github/workflows/ci.yml](.github/workflows/ci.yml)):

1. 确认 `main` 绿灯(backend / frontend / migrations 三个 job 通过)。
2. 更新 `CHANGELOG.md`:把 `[Unreleased]` 内容整理到新版本标题下并注明日期,标注破坏性变更(⚠️)。
3. 打标签并推送:

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

4. `v*` 标签触发 CI 的 `images` job,构建并推送**双架构(amd64 + arm64)**镜像到 GHCR:
   - `ghcr.io/sine-io/course_scheduling_system-api`
   - `ghcr.io/sine-io/course_scheduling_system-worker`
   - `ghcr.io/sine-io/course_scheduling_system-web`

   每个镜像会推 `:latest`、`:<版本标签>`(如 `v1.0.0`,即 `github.ref_name`)与 `:<commit sha>` 三个 tag。`main` push 仅建 amd64;**版本标签才建双架构**。
5. 在 GitHub 创建 Release,关联该标签,粘贴该版 CHANGELOG 内容。
6. 用户升级：在 `.env` 中设置 `IMAGE_TAG=v1.0.0`，然后执行 `sudo docker compose pull && sudo docker compose up -d`（见 [升级说明](docs/deploy/upgrade.md)）。`IMAGE_TAG` 对应此处推送的版本标签。

## 授权

贡献即表示你同意以 [MIT](LICENSE) 授权释出你的贡献。
