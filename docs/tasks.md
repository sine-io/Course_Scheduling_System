# 开发交棒计画 — Milestone 与任务卡

> 版本:v1.0(2026-07-07)
> 前置阅读:**[architecture.md](architecture.md)**(需求、数据模型、引擎设计、技术栈均以该文件为准)
> 使用方式:开发 AI(Opus 4.8 / Sonnet 5)每次领取**一张任务卡**,实现 → 依「验收标准」自我验证 → 报告 → 经用户验收后才进下一张。
> 任务卡状态标记:`[ ]` 未开始 / `[~]` 进行中 / `[x]` 已验收。开发者完成后请直接更新本文件的复选框。

---

## 项目目录结构(M0 创建,整个项目遵循)

```
Course_Scheduling_System/
├── docker-compose.yml          # 正式部署用(5 容器:caddy/api/worker/postgres/redis)
├── docker-compose.dev.yml      # 开发用(热重载)
├── .env.example                # 仅需改:管理员密码、校名、SMTP(选填)
├── Caddyfile
├── docs/                       # 本规划文件 + 用户文件
│   ├── architecture.md
│   ├── tasks.md
│   └── deploy/                 # 中文部署图文教学
├── backend/
│   ├── pyproject.toml          # uv 管理;ruff + pytest 设置
│   ├── alembic/                # 数据库迁移
│   ├── app/
│   │   ├── core/               # 设置、DB session、auth、安全
│   │   ├── models/             # SQLAlchemy models(对应 architecture.md §2.2)
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── api/                # routers(依资源分档:teachers.py、timetables.py …)
│   │   ├── services/           # 商业逻辑(冲突检查、代课推荐、导入导出…)
│   │   ├── solver/             # OR-Tools CP-SAT 排课引擎(独立、不 import app 其他层)
│   │   │   ├── model_builder.py    # 约束建模
│   │   │   ├── conflict_explainer.py # 无解冲突定位
│   │   │   └── preflight.py        # 排课前置检查
│   │   ├── workers/            # RQ 任务(排课、发送邮件、备份)
│   │   └── main.py
│   └── tests/
│       ├── fixtures/           # 三套学制验证数据集(见测试策略)
│       ├── unit/
│       └── solver/             # 引擎正确性测试
├── frontend/
│   ├── package.json            # pnpm;Vue 3 + TS + Vite + Pinia + Naive UI
│   ├── src/
│   │   ├── api/                # API client(openapi-typescript 生成类型)
│   │   ├── stores/
│   │   ├── components/
│   │   │   └── timetable/      # TimetableGrid 拖拽课表组件(核心)
│   │   ├── views/              # 依信息架构分页(见 architecture.md §5.1)
│   │   └── router/
│   └── e2e/                    # Playwright
└── .github/workflows/ci.yml    # lint + test + 双架构 image build
```

---

## Milestone 总览

| Milestone | 目标 | 完成的可见成果 |
|---|---|---|
| M0 项目骨架 | 可运行的基础系统 | `sudo docker compose up -d` 后可登录并看到空仪表盘 |
| M1 基础数据 | 构建学校数据 | 设置向导走完,教师/班级/科目/教室/场地齐备 |
| M2 手动排课 | 拖拽排课可用 | 手动排完一张班级课表并发布,教师可查询 |
| M3 自动排课 | 引擎上线 | 一键生成自动排课草稿，无解时提供易懂的原因说明 |
| M4 调课与代课 | 学期中日常运行 | 请假→代课→通知→确认 全流程 |
| M5 报表与上线 | 对外可发行 | 导出/备份/部署文件完成,可发布 v1.0 |
| M6 v1.1 加固 | 排课季前的体验与韧性 | ops 队列拆分、部分排课不中断整体流程等五项,发布 v1.1(范围见 docs/roadmap.md) |
| M7 v1.2 易用性 | 降低首次安装与体验成本 | 一键安装、学校信息设置、超课时上限和离线文档；示例数据能力后由 ADR-0006 撤回 |

---

## M0 项目骨架

### [x] M0-1 Repo 初始化与 Docker Compose 骨架
- **描述**:创建上述目录结构;`docker-compose.yml`(5 容器)与 `docker-compose.dev.yml`;FastAPI hello endpoint(`GET /api/health`);Vue 3 空项目由 Caddy 服务;Alembic 初始化;`.env.example`。
- **模块**:根目录、`backend/app/main.py`、`frontend/`、`Caddyfile`
- **验收标准**:
  1. 在全新机器上执行 `cp .env.example .env && sudo docker compose up -d` 后，浏览器打开 `http://localhost` 可看到前端页面，`/api/health` 返回 `{"status":"ok"}`
  2. 执行 `sudo docker compose ps` 后，所有容器均为 healthy
  3. dev compose 支持前后端热重载
- **测试方式**：在 CI 中执行 `sudo docker compose up` 并使用 curl 完成冒烟测试

### [x] M0-2 账号、登录与 RBAC
- **描述**:`user`/`user_role` model 与迁移;bcrypt + session cookie 登录;RBAC 依赖注入(admin/scheduler/director/teacher);首次启动以 `.env` 创建 admin;首次登录强制改密码;登录页 UI。
- **模块**:`app/core/auth.py`、`app/api/auth.py`、`app/models/user.py`、`frontend/src/views/Login.vue`
- **验收标准**:
  1. admin 可登录/登出;错误密码 5 次锁定 15 分钟
  2. 未登录调用受保护 API 回 401;teacher 角色调用 scheduler API 回 403
  3. 首次登录被导向改密码页,改完才能进系统
- **测试方式**:pytest(auth 流程 8+ 案例)+ Playwright 登录 E2E

### [x] M0-3 CI 与程序质量基线
- **描述**:GitHub Actions:ruff + mypy + pytest / eslint + vitest / Playwright / 双架构(amd64+arm64)image build push。pre-commit 设置。
- **验收标准**:PR 触发全部检查;main 分支 push 产出 image;README 挂 CI badge
- **测试方式**:开测试 PR 验证

---

## M1 基础数据管理

### [x] M1-0 地基补强(M0 架构检查产出,先做完才进 M1-1)
- **描述**:检查发现三项「现在改便宜、日后改痛」的地基问题:
  1. **Session 撤销**:session token 由 `{"uid"}` 改为 `{"uid", "pv": password_hash[-12:]}`,`get_current_user` 验证 `pv` 与现行密码一致,不符回 401(改密码即失效所有旧 session);
  2. **naming_convention**:`Base.metadata` 加入标准约束命名惯例(ix/uq/ck/fk/pk),确保跨数据库迁移可靠;
  3. **时区政策落地**（architecture.md D6）：系统固定使用 `Asia/Shanghai`，不提供部署时区选项。
- 顺手项:CI 增加「PostgreSQL service container 跑 `alembic upgrade head`」迁移验证步骤;前端 `client.ts` 加 401 全域处理(清 store → 导向登录)。
- **模块**:`app/core/{security,auth,db,config}.py`、`tests/`、`.github/workflows/ci.yml`、`frontend/src/api/client.ts`
- **验收标准**:
  1. 登录后改密码,以「旧 cookie」调用 `/api/auth/me` 回 401(新增 pytest 案例)
  2. `Base.metadata.naming_convention` 已定义,`alembic upgrade head` 在 PostgreSQL 全新数据库成功(CI 验证)
  3. session 过期或被撤销后,前端任何 API 操作自动导回登录页
  4. 现有 15 个 auth 测试不退步
- **测试方式**:pytest + CI 迁移 job

### [x] M1-1 学期与作息时间表
- **描述**：`semester` / `period_table` / `period` CRUD（model + API + UI）；作息时间表可视化编辑器；公开模板收敛为“初中（空白模板）”，仅包含科目参考项和空白作息时间表；同一学期可维护多套作息时间表。
- **模块**:`app/models/{semester,period}.py`、`app/api/semesters.py`、`frontend/src/views/settings/PeriodTable.vue`
- **验收标准**:
  1. 可创建“2026-2027学年第一学期”，选择“初中（空白模板）”后不默认设置节次、铃声、周课时或校历
  2. 可将周五第 7 节改为「班主任时间」,排课时段检查 API 即反映
  3. 可为同学期建第二套作息时间表并指派给不同班级群
- **测试方式**:pytest CRUD + 模板加载;Vitest 组件测试

### [x] M1-2 教师、班级、科目、教室与功能教室 CRUD
- **描述**:四实体完整 CRUD(对应 architecture.md §2.2 字段);教师任教科目多选、行政职减课、企业兼职教师标记;班级的学制标签与专业类别(中职);教室/场地类型与容量;列表页支持搜索/排序。
- **模块**:`app/models/`、`app/api/`、`frontend/src/views/basedata/`
- **验收标准**:
  1. 四实体均可增删改查,删除有引用检查(被教学任务引用的教师不可删,提示改为「离职」状态)
  2. 教师页可设置「不可排时段」与「偏好时段」(按周和节次点击格子)
  3. 中职班级可填专业类别;小学班级可指定班主任
- **测试方式**:pytest(含引用完整性案例)

### [x] M1-3 Excel 导入
- **描述**:教师、班级、科目三种 Excel 模板(系统内可下载,含填写说明行与示例行);上传→逐行验证→错误列表(「第 N 行:XX 原因」)→全对才事务性入库;导入教师时可勾选「同时创建账号」(默认密码规则+强制首登改密)。
- **模块**:`app/services/importer.py`、`frontend/src/views/basedata/Import.vue`
- **验收标准**:
  1. 下载模板→填 30 位教师→上传→全数入库且账号创建
  2. 故意填错(科目不存在、重复姓名+身份后四位)→报告确切行号与原因,数据库零写入
  3. 模板字段有中文说明列,导入时自动跳过
- **测试方式**:pytest 用 fixtures 内的正确/错误 Excel 文件

### [x] M1-4 设置向导
- **描述**:首次登录(无任何学期数据时)自动进入四步设置向导；依次完成学校与学期、基础数据、作息安排和完成检查。可保存退出并按真实数据继续；完成后导向教学任务管理；系统管理可检查并补全当前学期。当前行为由 ADR-0007 取代原五步设计。
- **模块**:`frontend/src/views/wizard/`、`app/api/wizard.py`(进度状态)
- **验收标准**:
  1. 全新系统登录即进入向导；完成基础设置后，仪表盘显示数据摘要（N 位教师、N 个班级）
  2. 中途关浏览器,再登录从上次步骤继续
  3. 用户测试：不看文档可在 30 分钟内创建中性学期，录入基础数据并确认学校实际作息
- **测试方式**:Playwright E2E 全向导流程

### [x] M1-5 开新学期复制向导
- **描述**:从现有学期复制教师/班级/科目/教室/场地/作息时间表到新学期(可勾选项目);班级年级自动 +1(可关闭),毕业年级提示移除。
- **验收标准**:复制后两学期数据独立(改 A 学期教师不影响 B);年级进位正确
- **测试方式**:pytest

### [x] M1-6 混合学制支持:班级 ↔ 作息时间表指派(M2 前必做,架构检查 2026-07-09 产出)
- **领域背景**：多数学校只需一套作息时间表；附设小学部、十二年一贯制实验学校或夜间部等场景可能需要多套作息时间表。设计原则是默认流程保持简单，仅在需要时提供扩展能力。
- **描述**:班级尚无「所属作息时间表」关联,M2 冲突检查/排课引擎无从得知每班合法时段。实现:
  1. `class_units.period_table_id`(nullable FK,空=学期默认作息时间表)+ 迁移;
  2. 班级表单增「作息时间表」下拉——**仅于该学期有 ≥2 套作息时间表时显示**(单一表学校完全看不到此字段);Excel 班级模板增「作息时间表」栏(选填,以名称对应);
  3. 提供 helper `resolve_period_table(class_unit)`(指定表 → 回退学期默认表),**无论单表或多表学校,M2 起所有时段逻辑统一走此函数**;
  4. 删除作息时间表时检查是否被班级引用(引用中则挡)。
- **模块**:`app/models/basedata.py`、`app/api/basedata.py`、`app/services/importer.py`、`frontend/src/views/basedata/ClassesTab.vue`
- **验收标准**:
  1. 完全中学场景:同学期两套作息时间表(初中 45 分/高中 50 分),301 班指到初中表、501 班指到高中表,各自 available-slots 正确
  2. 未指派作息时间表的班级回退学期默认表
  3. 被班级引用的作息时间表删除时回 409
  4. Excel 导入班级可指定作息时间表名称,名称不存在时报行号错误
- **测试方式**:pytest(完全中学 fixture 场景)

---

## M2 教学任务与手动排课

### [x] M2-0 教师账号绑定与联系信息(M1 检查 2026-07-09 产出,M2-1 前必做)
- **背景**:`user.py` docstring 承诺的 User↔Teacher 绑定在 M1 未实现(导入建账号仅存 display_name,无外键)。此绑定是 M2-5「教师查本人课表」、M4 全部(请假自登、代课确认、通知收件人)的前提。另用户需求:教师需有联系字段以利调课与代课通知。
- **描述**:
  1. `teachers.user_id`(nullable FK → users,`ondelete=SET NULL`,同学期唯一 uq(semester_id, user_id));Excel 导入「同时创建账号」时自动绑定;教师表单(admin/scheduler)可选择绑定现有账号;
  2. `teachers.email` / `teachers.phone` / `teachers.line_id`（均为可空字符串）——联系信息保存在教师学期快照中，外聘或企业兼职教师即使没有系统账号也能维护联系信息；
  3. Excel 教师模板增加电子邮箱、手机号和即时通讯账号三个选填字段；教师表单同步增加这些字段；
  4. `semester_copy` 复制 user_id 与三个联系字段(绑定跨学期延续);
  5. helper `current_teacher(db, user, semester_id)`:由登录者解析其在指定学期的教师基础信息(M2-5/M4 共用)。
- **模块**:`app/models/basedata.py`、`app/services/{importer,semester_copy}.py`、`app/api/basedata.py`、`frontend/src/views/basedata/TeachersTab.vue`
- **验收标准**:
  1. 导入 30 位教师勾「创建账号」→ 每位教师的 `teachers.user_id` 正确绑定新账号
  2. 开新学期复制后,新学期教师仍绑定同一账号、联系信息完整
  3. 同一账号在同学期绑第二位教师 → 409
  4. Email 格式错误时表单与导入均报告错误
- **测试方式**:pytest(绑定/复制/唯一性);现有导入测试不退步

### [x] M2-1 教学任务管理
- **描述**:`scheduling_unit`/`course_assignment`/`assignment_teacher`/`block_rule` model 与 CRUD;教学任务创建 UI(班级选科目→指定教师→周节数→连堂→教室/场地需求);走班群组创建(选多班级组成 group,群组内置多项教学任务);教师课时实时统计侧栏(教学任务数 vs 基本课时,超/不足变色);Excel 批量导入教学任务。
- **模块**:`app/models/assignment.py`、`app/api/assignments.py`、`frontend/src/views/scheduling/Assignments.vue`
- **验收标准**:
  1. 可创建“301 班 × 语文 × 王老师 × 每周 5 节”和“高二选修课程走班分组（3 个班、5 门课程）”
  2. 可创建「机械科实习 × 2 位协同教师 × 每周 6 节含 3 连堂×2」
  3. 王师配 22 节、基本课时 20 → 侧栏显示「+2 超课时」红字
  4. 班级周教学任务总节数 > 可排节次数(经 `resolve_period_table`+`regular_slots`)时警告
  5. 走班群组成员班级的作息时间表不一致 → 创建被拒(architecture.md D7 第 4 点)
- **测试方式**:pytest(含走班/协同/连堂三种结构)

### [x] M2-2 TimetableGrid 课表组件
- **描述**:前端核心组件:CSS Grid 周课表,依作息时间表渲染(含反灰不排课时段);单元格卡片(科目、教师、教室/场地、锁定图示);HTML5 拖拽(从未排列表拖入、格间移动、拖出移除);视觉状态(可放绿框/冲突红框+原因浮窗);响应式(平板可用,手机只读)。**纯展示+事件组件,不含商业逻辑**。
- **模块**:`frontend/src/components/timetable/`
- **验收标准**:
  1. Storybook(或示范页)展示:小学 40 分作息时间表与中职 50 分作息时间表各一张
  2. 拖拽过程触发 `check` 事件、放下触发 `drop` 事件,由父层决定结果
  3. Vitest 组件测试涵盖渲染/拖放事件/锁定显示
- **测试方式**:Vitest + 示范页人工查看

### [x] M2-3 冲突检查服务与手动排课 API
- **描述**:`timetable`/`schedule_entry` model;冲突检查服务(H1–H10 硬约束的单格检查版,architecture.md §3.2);**教师和教室/场地的冲突在跨作息时间表时以墙钟时间区间重叠判定**(architecture.md D7,同表退化为 period_no 相等);API:创建草稿、单元格增删改、`POST /timetables/{id}/check-conflict`(<100ms)、锁定/解锁;走班群组拖一格连动全组。
- **模块**:`app/services/conflict_checker.py`、`app/api/timetables.py`
- **验收标准**:
  1. 王师已在周一第一节有课,再排他班同时段 → 回冲突「教师王师 周一第一节 已有 302 班数学」
     (时段统一以**作息时间表中的名称**呈现:早自习/午休/第一节,不可用内部 period_no 索引)
  2. 连堂课拖至跨午休位置 → 拒绝并说明
  3. 走班群组某组拖到新时段,全组连动;任一组冲突则整组拒绝
  4. check-conflict 在 60 班数据量下 p95 < 100ms
  5. 跨作息时间表冲突:王师在小学部(40 分/节)周一第 4 节 10:30–11:10 有课,再排他至高中部(50 分/节)周一第 3 节 10:10–11:00 → 报告冲突(墙钟时间重叠)
- **测试方式**:pytest 覆盖 H1–H10 每项至少 2 案例(过/不过);性能测试脚本

### [x] M2-4 排课工作台整合
- **描述**：整合 M2-2 组件与 M2-3 API，形成完整排课工作台：左侧显示未排教学任务及剩余节数，支持班级、教师、教室/场地三种视角切换，草稿自动保存，并提供撤销/重做操作。
- **模块**:`frontend/src/views/scheduling/Workbench.vue`
- **验收标准**:
  1. 以初中 fixtures 手动排完一个班整周课表,未排列表归零
  2. 三视角数据一致(班级视角排的课,教师视角立即可见)
  3. Ctrl+Z 可撤销最近 20 步操作
- **测试方式**:Playwright E2E「排完一班」场景

### [x] M2-5 版本管理与发布
- **描述**:多草稿并存(复制/改名/删除);发布(draft→published,同学期旧 published 转 archived);发布前完整性检查(未排完教学任务列警告,可强制发布);全员课表查询页(按班级、教师或教室/场地查询,只读,手机可用);audit_log 记录发布。
- **验收标准**:
  1. 两份草稿可并存互不影响;发布 B 后,查询页显示 B,A 仍可编辑
  2. 有 3 节未排时发布 → 出现警告列表,确认后仍可发布
  3. teacher 角色登录手机浏览器可查本人课表
- **测试方式**:pytest 状态转换 + Playwright

---

## M3 自动排课

### [x] M3-0 三套学制验证数据集(M2 检查 2026-07-10 产出,M3-1 前必做)
- **背景**:测试策略总则承诺的三套 fixtures(标注「M1 期间创建,整个项目共用」)实际从未创建——`backend/tests/fixtures/` 目录不存在,M1–M2 测试均在各测试文件中临时构造小数据。M3-1/2/3/5 与 M5-4 的验收全部以「三套 fixtures」为前提;不先补齐,每张 M3 卡会各自构造数据,求解质量彼此不可比。
- **描述**:以 Python builder 函数(非静态 JSON,直接用 models 写入测试 session)实现三套数据集:
  1. `elementary_small`:小学 6 班(包班+任课教师、周三下午空、班主任时间);
  2. `junior_high_mid`:初中 12 班(学科课程+弹性课程+兼行政减课教师);
  3. `vocational_high`:中职 15 班 3 科(3 连堂实习+实训场地+企业兼职教师 unavailable 时段+走班群组);
  4. 各附烟雾测试证明数据自洽:teacher_loads 无超课时、class_loads 不超可排节数、走班群组同作息时间表。
- **模块**:`backend/tests/fixtures/{__init__,elementary,junior_high,vocational}.py`
- **验收标准**:
  1. 三套 builder 可在干净测试 DB 建出完整学期(作息时间表/教师/班级/科目/教室/场地/教学任务/连堂/时段规则)
  2. 烟雾测试通过(数据自洽,可被 CP-SAT 排出全解)
  3. 现有 135 个后端测试不退步
- **测试方式**:pytest

### [x] M3-1 Solver 数据层与 pre-flight 检查
- **描述**:`solver/` 模块骨架:从 DB 读取学期数据转为纯 dataclass 问题描述(solver 不碰 SQLAlchemy;**DB→dataclass 转换层放 `app/services/solver_data.py`**,因 loader 必须 import models,放 solver/ 内会违反验收 3);pre-flight 必要条件检查(教师教学任务数≤可排格数、教室/场地供需、班级节数,architecture.md §3.4)+ 班级人数>教室/场地容量警告(D8);检查报告 API。
- **补遗(M2 检查 2026-07-10)**:`schedule_entries.room_id`(nullable FK,空=沿用教学任务的 room_id)+ 迁移——§2.2 承诺单元格带教室/场地但 M2 未实现;solver 对「指定教室/场地类型而未绑定教室/场地」的教学任务需逐格指派教室/场地,结果无处可存(M4 教室变更也需要)。conflict_checker `_build_occupancy` 与课表序列化改以 `coalesce(entry.room_id, assignment.room_id)` 取教室/场地。
- **pre-flight「教师可排格数」定义**:单一作息时间表(绝大多数学校)=一般课格数 − unavailable 格数;跨表任教的教师以墙钟区间并集去重计数(D7 重叠矩阵)。
- **模块**:`app/solver/preflight.py`、`app/solver/problem.py`、`app/services/solver_data.py`
- **验收标准**:
  1. 三套 fixtures(M3-0)均可转出问题描述且 pre-flight 通过
  2. 人为制造「王师 22 节但可排 20 格」→ 报告明确指出教师、数字
  3. solver 模块 `import` 不到 `app.api`/`app.models`(以 import-linter 或测试保证)
  4. 手动排课将单元格放到与教学任务不同的教室/场地后,check-conflict 以单元格教室/场地判定占用
- **测试方式**:pytest

### [x] M3-2 CP-SAT 核心建模(硬约束)
- **描述**:实现 H1–H10 硬约束建模(architecture.md §3.2);连堂以区间建模;走班同步;锁定单元格;教室/场地互斥(D8);教师和教室/场地跨作息时间表时以 D7 重叠矩阵建模;求解取出结果转 schedule_entry 列表(含逐格 room_id)。
- **补遗(M2 检查 2026-07-10)**:
  1. `ortools` 依赖**此卡才加入** pyproject(M3-1 不需要,保持 pre-flight 轻量);注意 wheel 体积(~50MB)与 arm64 wheel 可用性,重建镜像验证;
  2. **H10 精确定义以独立 validator 为准**:同班同科目每日「单节」数 ≤ 上限,连堂(block_rule 生成)的节数不计入;M2-3 手动 conflict_checker 目前把现有连堂 span 也计入每日计数,与此不一致,此卡顺手对齐(改法:占用索引的 subj_count 排除 span>1 或挂 block_rule 的单元格)。
- **模块**:`app/solver/model_builder.py`
- **验收标准**:
  1. 三套 fixtures 各自可解,且**逐项验证**解零硬约束违反(以独立 validator 检查,不信任 solver 自己)
  2. 中职 fixture 的 3 连堂课全部连续且不跨午休;实训场地同时段不超容量
  3. 锁定 5 格后重解,该 5 单元格置不变
  4. 12 班初中 fixture 在 CI 机器 60 秒内解出
- **测试方式**:`tests/solver/` + `validator.py`(独立验证器,亦供日后回归)

### [x] M3-3 软约束与目标函数
- **描述**:实现 S1–S8 软约束(architecture.md §3.2)加权目标;权重设置存 DB(`constraint_config`,含 H10 每日上限值),UI 于 v2 才做,先用默认值;解出后产出「软约束达成度报告」(各项得分/满分、未达成明细)。**补遗**:`subjects.is_major`(主科标记,S5 用)+ 迁移 + 科目表单勾选——现行 Subject 无此字段。
- **验收标准**:
  1. 同 fixture 开/关 S2(同科分散)比较:开启后同班同科目同日 ≥2 节的数量显著下降
  2. 教师 avoid 时段在有替代方案时被避开
  3. 报告列出“王老师周四第 7 节已排课（偏好未满足）”等易懂的明细
- **测试方式**:pytest 比较性测试(断言方向性,不断言绝对分数)

### [x] M3-4 Worker 整合与进度报告
- **描述**:排课任务走 RQ:`POST /timetables/{id}/auto-schedule` 入队列;CP-SAT callback 每 5 秒写进度(已找到解的目标值、经过时间)至 Redis;前端进度页(polling)含「提前结束取目前最佳解」与「取消」;timeout 默认 10 分钟可设置;结果写回为新草稿。**输入输出流定义(M2 检查 2026-07-10)**:以来源草稿为输入;`locked` 单元格作为固定约束(H9)复制至结果草稿并保持锁定;未锁定的现有单元格以 CP-SAT hint(`AddHint`)喂入以提高解的稳定性(重排时尽量少动);结果草稿命名「{来源名} 自排结果」,来源草稿不动。
- **模块**:`app/workers/solve_job.py`、`frontend/src/views/scheduling/AutoSchedule.vue`
- **验收标准**:
  1. 启动排课后 UI 显示进度;点「提前结束」拿到当前最佳解草稿
  2. 排课期间 Web 其他功能不受影响(worker 隔离)
  3. worker 容器被 kill 后任务标记失败,UI 有明确错误而非永久转圈
- **测试方式**:pytest(RQ 假队列)+ Playwright 长流程

### [x] M3-5 无解冲突定位(conflict explainer)
- **描述**:冲突定位(architecture.md §3.4):无解时指出是哪几条硬约束凑在一起,转译为教务语言建议;「部分排课」模式(用户勾选可放宽的约束类别,将其转为高权重软约束,未排入教学任务列列表)。
- **模块**:`app/solver/conflict_explainer.py`
- **验收标准**:
  1. ✅ 制造「音乐教室需求 30 节 > 实际可用 28 节」的 fixture → 报告指出教室/场地与数字
  2. ✅ 制造教师时段矛盾 → 报告指出该教师(两位协同教师都点名)
  3. ✅ 部分排课模式:同 fixture 产出 97.8%(88/90)排入的草稿 + 未排列表
- **测试方式**:pytest(3 种人造无解场景 + 部分排课 + pre-flight 短路);Playwright ×2;真实 PostgreSQL + RQ 实测

**补遗(实现后)**
- **改用删除法,不用 assumption / unsat core**。原设计是每类硬约束挂 assumption literal 取 unsat core,实测不可行:enforcement literal 让 presolve 认不出鸽笼结构,同一份数据**纯硬约束 0.8 秒证完,挂 assumption 后 60 秒证不完**(换过三种编码均然)。改成「把一组约束整个关掉、重建干净模型重解」,整套定位约 2~3 秒,且每条结论都被一次真实求解验证过。
- 旋钮只取排课管理员改得动的东西:`H4` 教师不可排时段、`H3` 教室/场地互斥、`H10` 每日科目上限、`H9` 锁定单元格。`H1`/`H2` 没有旋钮可转,其成因 pre-flight 已算得出来。
- `H1`/`H2`/`H3` **永不可放宽**——那是物理不是政策(API 收到会回 400)。
- **超时且零解时也跑定位**:带软约束目标函数的 CP-SAT 常证不出 INFEASIBLE,统一以纯硬约束探测一次,才分得出「不可能」与「只是慢」。这是实际环境验证才发现的——单元测试里的小问题秒证无解,看不到这个坑。
- 部分排课的惩罚量级:未排入(10000) ≫ 放宽的约束(1000) ≫ 软约束(1~8);因此其 `objective` 与一般模式尺度不同,UI 显示「未排 N 节」而非目标值。
- 部分排课的 pre-flight 只挡结构性错误(连堂放不进、群组节数不一致、没有该类型的教室/场地)。
- 部分排课结果统一再过 `validator`:除了被放宽的那类,其余硬约束零违反。

---

## M4 调课与代课

### [x] M4-1 请假登记与受影响节次展开
- **描述**:`leave_request`/`affected_period` model;教师自登/排课管理员代登 UI;依 published 课表展开受影响节次(半天/多天/跨周假);销假(级联取消处理方式并通知,architecture.md §5.3 状态机)。
- **验收标准**:
  1. 王师请周三全天假 → 自动列出周三 5 节受影响课
  2. 请假 3 天跨周末 → 只展开上课日节次
  3. 销假后已指派代课的教师收到取消通知
- **测试方式**:pytest(日期边界:周末、学期起止外拒绝)

**补遗(实现后)**
- **`affected_period` 是快照,不是 join**(这是 M4 的地基决策):展开当下把教学任务/教师/班级/教室/场地/节次名称/起止时间一并写死。理由与 D4 一致——课表可以重新发布,但「王师 11/12 第三节原本要上 301 班语文」是既成事实,不该随课表改版漂移,更不该让一项已指派的代课隔天指向另一门课。溯源指标(schedule_entry_id/course_assignment_id)课表删除时 SET NULL,快照字段仍在。真机验过:删掉已发布课表后,受影响节次原封不动。
- **只看已发布课表**:草稿随时会变,拿草稿找代课老师没意义。课表未发布时假单照样成立,只是展开 0 节。
- **上课日由作息时间表决定**,不写死周一~周五:六日制学校的周六有课由 `num_weekdays` 判定(周末跳过 = `isoweekday() > num_weekdays`)。
- **半天假以墙钟时间区间重叠判定**;作息时间表没填起止时间时保守列入(宁可多列一节让排课管理员删,也不要漏掉一节变成没老师的教室)。多日假只有头尾两天受时间限制,中间全天。
- **销假级联**:已完成的节次不动(课上过了,课时照算);已指派代课的转为已取消并**合并**通知代课教师(一人多节一封信);当事人另收销假通知。这条在 M4-1 就做掉,不留到 M4-3。
- **通知只落地、不发送**:`notifications.notify()` 是 M4-3 `NotificationChannel` 的写入点;写入永远成功,发送(站内铃铛/Email)可失败可重试,不与同一事务绑定。
- **RBAC**:教师自登只能登自己、只看自己;排课管理员/主任可代登代销看全校。教师端请假页手机可用(路由守卫新增 `leaves` 为教师可进页面)。
- **前端**：日期统一附带星期（如“2026-11-11（星期三）”）；已取消状态使用弱化文字。日期按本地格式处理，不使用会引入 UTC 日期偏移的 `toISOString`。

### [x] M4-2 调课与代课处理工作台与推荐引擎
- **描述**:逐节处理 UI(代课/调课/合班/自习/不处理);**代课推荐服务**:硬性过滤(该时段空堂、当日未请假)→ 排序(同科目 > 当日已在校 > 本月代课课时少),每位候选附排序理由;调课(swap)验证(architecture.md §5.3);指派即生效(**不设置邀请/拒绝流程**,2026-07-09 用户确定:实际工作中,排课管理员已事先口头征得同意,通知仅用于正式告知和确认收到)。
- **模块**:`app/services/substitution_recommender.py`、`frontend/src/views/substitution/`
- **验收标准**:
  1. 推荐列表第一名必为空堂+同科;已满 6 节者排序靠后
  2. swap 后任一方冲突 → 拒绝并说明是谁在哪一节冲突
  3. 该时段全校无人空堂 → 显示「无可代教师」并建议合班/自习
- **测试方式**:pytest 推荐排序表格测试(10+ 场景)

**补遗(实现后)**
- **「周格 vs 特定日期」的落差用独立的 `availability.py` 收敛**(Fable 5 M3 审查点名的 M4 最大架构工作):可用性判断叠三层——周课表有没有课(D7 墙钟重叠)、当天自己有没有请假、当天有没有被指派代别班。今日看板(M4-4)与代课推荐共用这一层。
- **当日请假必须读假单本身的日期/时间窗,不是展开的 `affected_period`**——这是实现时测试抓到的真 bug:老师请全天假、但某节恰好是他的空堂时,`affected_period` 不涵盖那一格(它只在有课的节次才存在),若照它判断会把一位不在校的老师找来代课。改为直接比对 `leave_request` 的 start/end 日期时间(与 `leaves.expand` 同一套半天窗语义)。
- **推荐排序**：同科目 > 当天已在校 > 本月代课课时少 > 姓名（保证顺序稳定）。每位候选人均附易懂的推荐理由（如“同科目教师 · 当天已在校 · 本月已代 2 节”），不只显示无法解释的分数。
- **swap(调课)验四件事**:乙在甲那节无课、swap_entry 确是乙的课、甲在补课那节无课也没请假、补课日星期与该节课相符。任一撞课指名道姓拒绝。swap 交换的节次以快照保存(swap_date/period_name/class_names/subject_name),课表改版不影响已成立的调课。
- **课时政策**:代课计、合班/自习/不处理不计(可覆盖),供 M4-5 月结。`substitution` 是处理方式真相来源,`affected_period.handler_teacher_id`/`status` 为冗余指标。
- **指派即生效**：创建处理方式后，节次转为“已处理”并记录处理教师，再向处理教师发送通知。撤回处理方式后退回“待处理”并发送取消通知。不设置邀请或婉拒流程（2026-07-09 确定）。

### [x] M4-3 通知系统
- **描述**：`notification` 模型；通知发送采用 `NotificationChannel` 接口（architecture.md §5.3，MVP 实现站内通知和电子邮件，v2 可增加 webhook 适配器）；收件人通过 `teachers.user_id`（站内通知）和 `teachers.email`（电子邮件，M2-0 字段）解析；站内通知提供通知铃、未读数和轮询；电子邮件通过 RQ 发送（SMTP 在系统管理中配置，未配置时仅发送站内通知并提示）；包含代课指派、取消和课表发布模板；教师可在手机端一键“确认收到”；排课管理员可查看每条通知的确认状态，并再次提醒未确认人员。
- **验收标准**:
  1. 指派代课后,教师站内+Email 双通知,点链接直达确认页,一键「确认收到」
  2. 排课管理员于看板可见确认/未确认状态;对未确认者按「再次提醒」重发通知
  3. SMTP 未设置时系统正常运行(仅站内通知)
- **测试方式**:pytest(mailhog 容器拦信)+ Playwright 手机窗口尺寸

**补遗(实现后)**
- **NotificationChannel 分层**：`notifications.notify()` 创建站内通知记录后，逐一通过 `CHANNELS`（`InAppChannel` 和 `EmailChannel`）发送；v2 增加 webhook 时只需实现新渠道并加入列表。
- **Email 的事务语义**:EmailChannel 不直接 enqueue,而是把邮件放进 `session.info` 的发件箱;SQLAlchemy 的 `after_commit` 事件才排入 RQ,`after_rollback` 则丢弃——事务回滚就不会发送对应于不存在通知的邮件(解决双写问题)。已测试 rollback 不发送、commit 后才发送。
- **站内永远可用,Email 是加分**:SMTP 未设置时 `email.send` 回 False、`email_job` 只记 log,整个调课与代课流程照常。这是验收③,实际环境在 mailhog 上验过双通道。
- **SMTP 设置存 `app_settings`**(全域 key/value,非学期范围);密码留空 = 不变更,返回不含明文。管理员专属。`POST /settings/smtp/test` 当场寄测试信报告结果(不走 RQ)。
- **确认收到 = 通知层已读确认**,不影响教学任务(指派即生效,2026-07-09 确定)。教师铃铛(轮询 20s + 未读数 badge)、排课管理员看板(确认状态 + 对未确认者「再次提醒」重发,已确认则 409)。
- **开发用 MailHog**：docker-compose 增加 `mailhog`（profile 为 `dev`，不影响正式部署）；执行 `sudo docker compose --profile dev up` 后启动，Web 界面默认仅在本机端口 8025 开放，可通过 `.env` 的 `MAILHOG_UI_PORT` 调整。
- **E2E 教训**:共用 e2e_teacher 账号 + 发布课表的测试会用「最近学期」默认互相污染;测试中途失败会跳过收尾清理,故改用 `test.afterEach` 兜底删除学期。另 Naive 的 message toast 与 tag 同字符串会触发 strict-mode(getByText 命中两个),toast 文案要与 tag 区隔。

### [x] M4-4 今日看板与调课与代课日志
- **描述**：仪表盘“今日调课与代课看板”（当天全部变更：代课关系、教室变更）；支持打印当日调课与代课通知单（A4 公告格式），并按教师、日期和请假类型查询历史记录。
- **验收标准**:
  1. 看板实时显示今日已处理的调课与代课；没有变更时显示“今日无调课与代课”
  2. 打印版面 A4 一页内,含节次/班级/原教师/代课教师
- **测试方式**:Playwright 快照

**补遗(实现后)**
- **看板/日志不新增真相,只摊平**:`substitution_log.py` 把「受影响节次 + 处理方式」join 成一列列可读记录,今日看板与历史查询共用同一 `LogEntry`。真相仍在 `affected_period`(快照)与 `substitution`(处理方式决定)。
- **“今日”固定按 `Asia/Shanghai` 判定**，不直接使用 UTC 日期（D6）。前端链接可通过 `?date=&semester_id=` 指定日期，未指定时以后端 `school_today()` 为准。
- **看板含待处理节次**,好让排课管理员一眼看出还有几节没排代课;排除已销假(cancelled)的节次(那天没有变更)。打印通知单则只列已安排的处理方式(公告只公告已确定的)。
- **历史查询的 `teacher_id` 同时比对缺课当事人与接手代课者**——查一位教师,他缺的课与他代的课都算相关(以冗余的 `affected_period.handler_teacher_id` 命中接手方)。
- **A4 打印页是独立路由 `/daily-board/print`**(不使用侧边栏布局),通过 `window.open` 打开新页面;`@media print` 隐藏工具栏、设置 `@page A4`。校名取自 config.school_name,随看板响应返回(无需另行设置)。
- **注意事项:`date`/`start_time` 字段名遮蔽 datetime 类型**——dataclass/pydantic 内字段命名为 `date` 后,同类别后续以 `date` 标注类型会被 mypy 视为「用变量当类型」而报错。以模块别名 `_Date = date` 标注类型解决。

### [x] M4-5 代课课时统计
- **描述**:月结统计:依教师汇total(代课节数、计费节数——合班/自习不计、请假类型、经费来源标记);Excel 导出;教师个人可查本人明细。
- **验收标准**:
  1. fixture 一个月 20 条处理记录 → 统计数字与手算一致(含不计费项排除)
  2. 导出 Excel 字段:教师/日期/节次/班级/科目/原教师/请假类型/计费
- **测试方式**:pytest 计算正确性(边界:跨月假单拆月计)

**补遗(实现后)**
- **两个数字**:代课节数(所有接手处理方式:代课/调课/合班)vs 计费节数(`counts_toward_hours` 为真者)。自习/不处理没有处理教师,不计入任何人;合班有接手者但默认不计费(可覆盖)。「合班/自习不计」指的是计费,不是代课节数。
- **跨月假单自动拆月**:以每一个 `affected_period` 自己的日期分月,不是以假单分月。王师请 1/30~2/2,1 月的节次进 1 月报表、2 月的进 2 月,无需特别处理。
- **销假的节次不计但已完成的保留**:`leaves.cancel` 把未完成节次转 `cancelled`(那堂课没上)、保留 `completed`(课上过了课时照算);统计以 `affected_period.status != cancelled` 过滤,不看假单状态(才不会漏掉部分销假的已完成节次)。
- **RBAC**:排课管理员/主任看全校并导出 Excel(`/substitution-stats` + `/export`);教师只能查自己(`/substitution-stats/mine`,以 current_teacher 绑定解析,无绑定回空报表)。前端同一页依角色分流:管理者有教师筛选+导出钮,教师版隐藏。教师页加入路由守卫白名单。
- **Excel 两张表**:汇总(教师/代课节数/计费节数)+ 明细(教师/日期/节次/班级/科目/原教师/请假类型/处理方式/计费/经费来源);沿用 importer 的 openpyxl Workbook + FastAPI Response(Content-Disposition attachment)。前端以 `window.open` 带 cookie 触发下载。
- **深链接**:统计页与看板页一样支持 `?year=&month=&semester_id=`,便于分享与测试。

### M4 里程碑复审(Fable 5,2026-07-11)与修正
- **条件 A(已修)——「已完成」不落盘,改读取时推导**:§5.3 的「已确认→已完成:上课日结束自动转换」原本无任何程序写入 `completed`,导致两道完整性保护失效(销假会抹掉已上过课的课时、可事后改派已上完的代课)。改为 `app/core/clock.py` 的 `is_past_slot(date,end_time)`(以固定的 `Asia/Shanghai` 判定):`leaves.cancel` 对已上过的节次不转 cancelled、`substitutions.assign/clear` 对已上过的节次回 409;显示层 `leaves.effective_status()` 把 resolved+已过推导为 completed。M5-2 的 RQ scheduler 上线后可再补夜间 sweep 落盘,但正确性不依赖调度。
- **条件 B(已修)——swap 补课判定漏比对教师**:`availability._already_covering` 的 swap 分支原本只比对 `swap_date`+`period_no`,任一项调课成立后补课日该节次会误判**全校**已占用。改为 join `AffectedPeriod→LeaveRequest` 加 `teacher_id`(补课方=该调课请假的当事人)+ `status=registered` + 节次未取消。
- **条件 C(已修)——公平计数含幽灵代课**:`_monthly_sub_counts` 未排除已销假节次,销假后那项代课仍计入「本月已代 N 节」,与 M4-5 统计口径不一。加 `status != cancelled`。公平计数保持以**计费节数**(counts_toward_hours)计,与显示的「本月已代 N 节」一致。
- **条件 E(已处理)**:(1) 看板与统计口径差已记于补遗(唯一分歧=销假假单中已完成的节次:不上看板但计课时,合理);(2) swap 补课可用性退化为 period_no 比对,跨作息时间表学校有 D7 精度损失,列 v1.x;(3) `notifications` 的 after_commit enqueue 失败改为 `logger.warning` 留痕,不再静默忽略。
- **条件 D(排入 M5-0)**:学期中重新发布课表后,未来日期的 `affected_period` 仍指向旧单元格——见 M5-0。

---

## M5 报表、备份与发行

### [x] M5-0 发行前置(Fable 5 建议,M5-1 前必做)
- **描述**:一次备妥 M5 各卡的共用基础设施,避免每张卡各自处理环境。
  1. **PDF/字体基础**:worker 镜像安装 WeasyPrint 系统依赖(Pango/Cairo/gdk-pixbuf)与**中文内嵌字体**(Noto Sans CJK SC / Noto Serif CJK SC),供 M5-1 PDF、M5-2 之后的报表共用。字体与重量级系统依赖只装在 worker(导出走后台任务),api 镜像保持精简。
  2. **RQ scheduler 骨架**:立起定时任务调度器(M5-2 每日备份、条件 A 选配夜间 sweep 都挂这里);docker-compose 加 scheduler 服务,先跑一个 heartbeat/no-op 周期任务验证存活。
  3. **性能 fixture**:以 M3-0 的学制 builder 长出 60 班规模数据集,供 M5-1「60 班批量 < 60 秒」与 M5-4 压测共用;先确认 builder 能生成该规模。
  4. **条件 D:重新发布重展开受影响节次**:`leaves.expand` 只在登记当下依当时 published 课表展开;学期中重新发布课表后,**今日之后**的 pending/resolved 受影响节次仍指向旧单元格(代课老师被派去上已移走的课)。M5-0 先做最小防护——publish 时检测该学期「今日之后」的受影响节次数 > 0 就于响应与 UI 加警告;完整重跑 expand+diff+通知列为后续增强。
- **验收标准**:
  1. worker 容器内 `python -c "import weasyprint"` 成功,且以内嵌字体渲染中文 PDF 无 tofu(目视一张测试页)
  2. scheduler 服务启动后,周期任务有触发记录(log)
  3. 60 班 fixture builder 产出数据,基本查询正常
- **测试方式**:容器内 smoke test(WeasyPrint 导入 + 中文 PDF)、scheduler 存活记录、fixture builder pytest

**补遗(实现后)**
- **多阶段 Dockerfile(base / worker)**:api 用 `base`(精简),worker 用 `worker`(额外装 Pango/Cairo/gdk-pixbuf + `fonts-noto-cjk` + poppler-utils + `pip .[export]` 的 WeasyPrint)。compose 与 CI 均以 `target:` 指定;CI 另推 `-worker` 镜像。`app/services/pdf.py` 的 `render_pdf` 延迟导入 weasyprint,api 导入不会失败(导出统一走 worker 后台任务)。**实际环境验证**:worker 容器内 weasyprint 69.0 导入成功,渲染繁中 PDF→PNG 目视无 tofu(排课/调课与代课/王小明/语文/甲乙丙丁…/艺术与人文 均清晰)。
- **调度器骨架**:worker 已 `with_scheduler=True`;不加独立容器(单校部署少一个进程),改用「执行时排下一次」的自我续期心跳(固定 job_id,重启不堆叠),`ensure_scheduled()` 于 worker 启动时排入。M5-2 每日备份、条件 A 选配夜间 sweep 都挂此模式。**实际环境验证**:ScheduledJobRegistry 含 `scheduler-heartbeat`,手动触发 job 状态 FINISHED 且自我重排成功。
- **60 班性能 fixture**:`tests/fixtures/scale.py` 的 `build_large_school(num_classes=60)`,以贪婪「最少负载且不超 base」指派教师(不保证可完全排课,量为主);pytest 验 60 班 660 教学任务、无教师超课时。
- **条件 D 最小防护(已做)**:`timetable_publish.stale_future_affected_count` 算「今日之后、依先前课表展开」的待处理/已指派受影响节次;发布响应加 `stale_affected`,前端发布成功后 >0 则跳警告 toast(请至今日看板/调课与代课记录重新查看)。完整解(重跑 expand+diff+通知)仍列后续增强。

### [ ] M5-1 课表导出

### [x] M5-1 课表导出
- **描述**:班级、教师和教室/场地课表可导出为 Excel(openpyxl)、PDF(WeasyPrint,A4 纵向含校名/学期/打印日)或 PNG;另支持全校总表 Excel 和全部班级批量导出 zip。
- **验收标准**:
  1. 三种格式与页面课表内容一致;PDF 中文无乱码(内嵌字体)
  2. 60 班批量导出 < 60 秒
- **测试方式**:pytest 内容比对(Excel 读回验证)+ 人工查看 PDF 版面

**补遗(实现后)**
- **共用格线模型**:`timetable_export.py` 把已发布课表(D4 快照)摊成 `Grid`(节次列 × 星期栏,连堂以 span 合并),三种对象(班级=科目/教师/教室、教师=科目/班级/教室、教室/场地=科目/班级/教师)与三种格式共用,确保内容一致(验收①)。
- **Excel 在 api、PDF/PNG 在 worker**:openpyxl 轻量,班级、教师、教室/场地、全校总表和批量 zip 均由 api 同步生成。PDF 需 WeasyPrint(系统依赖+中文字体只在 worker,见 M5-0),故 PDF/PNG 由 api 以 `queue.render_export` **阻塞式**派到 worker 渲染再取回(RQ result);PNG = WeasyPrint 出 PDF 后 poppler `pdftoppm` 转单页。
- **全校总表 vs 批量**:总表=一个 Excel 文件,每班一个工作表;批量=每班各一个 Excel 文件并打包为 zip。单一课表导出开放给所有登录者(课表本就全校可查),总表/批量导出限排课管理员以上。
- **中文文件名**:Content-Disposition 用 RFC 5987 `filename*=UTF-8''`,前端以 fetch blob 下载并解出文件名(顺带处理 4xx/5xx 与加载状态)。
- **验收②**:60 班批量为 CPU-bound(60 个 openpyxl workbook),与数据库无关,pytest 用 `build_large_school` 实测 < 60 秒。**验收①**:E2E 下载班级 PNG(走 worker WeasyPrint→pdftoppm)存档目视:标题/校名/学期/打印日、节次×星期格线、早自习/午休淡色、周三第一节显示语文/王老师,繁中无 tofu。

### [x] M5-2 备份与恢复
- **描述**:每日 02:00 自动 pg_dump(保留 30 份,RQ scheduler);管理 UI:立即备份/下载/上传恢复(恢复前自动先备份现状+二次确认);恢复后强制全员重新登录。
- **验收标准**:
  1. 备份→改数据→恢复→数据回到备份点
  2. 上传非法文件被拒绝且系统无损
  3. 自动备份保留数正确轮替
- **测试方式**:pytest + docker 整合测试

**补遗(实现后)**
- **pg 工具版本**:基底镜像已是 Debian trixie(非 bookworm),其 main 内含 postgresql-client **17**;pg_dump 17 可备份 postgres:16 服务器(client ≥ server 允许)。原想从 PGDG 装 client 16,但 PGDG 的 libpq5 18 在 trixie 有依赖冲突,故直接用发行版的 client。pg 工具只装在 **worker** 镜像(与 M5-1 的 WeasyPrint 同层),api 保持精简。
- **跨版本恢复的可忽略错误**:pg_dump 17 的备份含 `SET transaction_timeout`(v17 GUC),pg_restore 恢复到 v16 服务器时会输出一条可忽略错误,exit code=1。按 pg_restore 约定(0=全部成功、1=完成但存在可忽略错误、>1=失败)允许 exit 1 并记录日志,数据仍能正确恢复(已实际验证回退成功)。
- **api/worker 分工**:列表/下载/上传由 api 直接读写共挂的 `backups` volume;pg_dump/pg_restore 派到 worker(`queue.run_backup`/`run_restore` 阻塞式)。每日备份挂 M5-0 的调度器(`schedule_daily_backup` 于 backup_hour 排 enqueue_at,执行后自我续期;固定 job_id 重启不堆叠)。
- **强制全员重新登录**:session 是无状态签名 cookie,恢复数据库不会使其失效。改在 **Redis** 记一个「最小有效签发时间」(`session_epoch`),恢复后设为现在;`get_current_user` 拒绝签发早于此的 session。Redis 只是被恢复的 PostgreSQL 之外的存放点。auth 端有 5 秒进程内缓存(fail-open),故强制登出有 ≤5 秒传播延迟(可接受)。
- **恢复后补写审计的坑**:恢复会 `pg_terminate_backend` 中止所有其他连接(含本请求的 DB 连接),且恢复本身会覆盖整个数据库——所以恢复前写的审计会被盖掉、恢复后用旧连接写会失败。正解:恢复后 `engine.dispose()` 再开新连接,把审计写进**恢复后**的数据库。
- **非法上传(验收②)**:`save_uploaded` 先验 `PGDMP` 魔数,非法直接拒绝、文件不落地、不碰数据库;恢复现有备份前也再验一次文件头。
- **实际环境验证(docker 整合)**:worker 内 pg_dump 17.10;备份→插入学期→恢复→条数回到备份点 ✅;轮替 3→keep=1→1 ✅;api POST /backups(RQ 阻塞)→201、POST restore→200(自动 presafe 备份)、/auth/me 由 200 转 401(强制登出,~5s)、重登 200 ✅;非法上传 400 且无文件落地(pytest)。

### [x] M5-3 部署文件与发行工程
- **描述**:`docs/deploy/` 中文图文:Docker 安装(Win/Linux/NAS)、三步骤安装、升级、备份策略、VPS+HTTPS 选配、常见问题;README(中文为主+英语摘要);CHANGELOG;GitHub Release 流程(tag→CI 出双架构 image);LICENSE(MIT);CONTRIBUTING.md。
- **验收标准**:
  1. 依文件在干净 VM 从零安装成功(实测)
  2. 执行 `sudo docker compose pull && sudo docker compose up -d` 从上一版本升级，数据保持完整且迁移自动执行
- **测试方式**:干净环境实测(记录于 PR)

**补遗(实现后)**
- **同一份 Compose，两种部署方式**：为支持 `sudo docker compose pull`，`docker-compose.yml` 中 web、api 和 worker 服务同时配置 `image:`（GHCR）与 `build:`。克隆源代码的用户执行 `sudo docker compose up -d` 时仍在本机构建；只获取部署文件的用户可执行 `sudo docker compose pull && sudo docker compose up -d` 拉取官方镜像。镜像版本由 `.env` 中的 `IMAGE_TAG` 决定，正式部署建议固定版本号。
- **CI 补版本标签**:原 `images` job 只推 `:latest` 与 `:sha`,`IMAGE_TAG=v1.0.0` 会拉不到镜像。三个镜像各补推 `:${github.ref_name}`(main push=`main`、版本标签=`v1.0.0`),版本固定才真的成立;版本标签仍为唯一触发双架构(amd64+arm64)的条件。
- **将 HTTPS 作为可选配置**：Caddyfile 原先将站点地址固定为 `:80` 并写入镜像，使用预建镜像的学校无法修改。现改为 `{$SITE_ADDRESS::80}` 环境变量；默认使用内网 HTTP，在 `.env` 中设置 `SITE_ADDRESS=域名` 后自动申请并续期 Let's Encrypt 证书。Compose 同时增加 443 端口映射和 `caddydata` 数据卷，用于持久保存证书并避免重复申请。验证结果：未设置域名时，重建 web 后 `/api/health` 与首页均返回 200，内网 HTTP 部署不受影响；`sudo docker compose config` 在两种配置下均可正确解析。
- **文件产出**:`docs/deploy/`(index/install/upgrade/backup/https/faq 六篇中文,含 Win/Linux/Synology/QNAP 安装、异地备份、回滚与 schema 变更提醒、VPS 对外端口与安全设置)、改写 `README.md`(英语摘要+功能总览+双部署快速开始+文件索引)、新增 `CHANGELOG.md`(Keep a Changelog,汇总 M0–M5)、`CONTRIBUTING.md`(开发环境/质量门槛/任务卡制/发布新版本流程)。`LICENSE`(MIT)M0 已具备。
- **验收①「干净 VM 实测」的界线**:compose 解析、web 重建与默认 HTTP 服务已在本机 Docker 验过;真正的「全新 VM 从零 pull 安装」需待版本标签推上 GHCR 后才可端到端跑(目前尚无 release tag),此步骤留给实际发布时(或用户)在干净环境验收并记录于 PR。

### [x] M5-4 E2E 总验收与性能
- **描述**:Playwright 全流程场景:向导构建→导入→教学任务→自动排课→发布→请假→代课→月统计;性能验收;无障碍基本检查(键盘可操作、对比度)。
- **验收标准**:
  1. 三套 fixtures 全流程 E2E 绿灯
  2. 60 班规模:页面加载 p95 < 2s、check-conflict p95 < 100ms、自动排课 < 10 分钟
  3. 以 4GB RAM 容器限制跑全流程不 OOM
- **测试方式**:CI E2E + 压测脚本

**补遗(实现后)**
- **验收①分两面落实**:(a) 后端 `tests/test_full_flow.py` 对**三套学制 fixtures**(小学/初中/中职)各跑完整流程——求解 → validator 验零硬违反 → 发布快照 → 挑一位有课教师请全天假 → 依已发布课表展开受影响节次 → 用推荐挑空堂教师指派代课 → 月结统计数字对上;证明下游链路能吃真实求解结果并在三种学制一致成立(M3 只证到「解得出」)。(b) 前端 `full-journey.spec.ts` 一个学期连续走完自动排课(真实 solver worker)→ 版本发布 → 课表查询 → 请假+代课(API)→ 月结(UI),截图目视:自排「已找到 16 个解、生成草稿A 自排结果」、月结页「语文师1 代 语文师2 事假 1 节、计费 1 节」。个别旅程细节仍由现有 26 支 spec 深入覆盖。
- **注意事项:全流程测试的两个时间性地雷**。(1) 求解要用 **hard-only config**(`SolverConfig.hard_only()`),否则挂软约束目标函数的 CP-SAT 会为了逼近最佳跑到 `max_seconds` 天花板——三套 fixtures 各跑 120 秒共 6 分钟;改 hard-only 后全部 15 秒。(2) 学期起止必须设在**今日之后**:代课处理方式会用 `clock.is_past_slot` 拒绝已结束的节次,起初用 2025 的日期整批被判为「已结束」而指派失败。
- **验收②（check-conflict p95 < 100ms）**：`tests/test_perf_scale.py` 使用 `build_large_school(60)`（660 条教学任务）创建 1500 多个合法占用格，执行 30 次单格冲突检查并统计 p95。**页面加载 p95 < 2s**：`perf-page-load.spec.ts` 在包含 60 个班的完整测试环境中测量。最初通过重复 `page.goto` 刷新整个页面，教学任务页 p95 约为 2.9s；这包含了每次重新下载并解析约 1.4MB SPA 资源的成本，并不等同于用户在应用内切换页面的延迟。改为测量资源已加载后的应用内导航后，教学任务页和课表查询页 p95 为 85–89ms；冷启动首次加载另计为 1069ms，两项均低于 2s。资源体积优化继续列入待办。**自动排课 < 10 分钟**：60 班求解不放入每次运行的 CI 单元测试，由 M3 的初中夹具在 60 秒内完成的建模测试和全流程实测共同验证。
- **验收③（4GB 内存下不发生 OOM）**：新增 `docker-compose.limits.yml`（叠加在正式 Compose 上，`mem_limit` 合计 3.2GB：worker 1.5GB、API 768MB、PostgreSQL 512MB、Redis 256MB、Web 128MB，约为主机保留 0.8GB）。在此限制下重建完整环境并运行全流程（含真实求解器）；`sudo docker stats` 记录的峰值为 API 132MB/768MB、PostgreSQL 36MB/512MB，小规模学校求解时 worker 仍有余量；全部五个容器均为 `OOMKilled=false`、`Restarts=0`。该文件也可作为 4GB 主机或 NAS 的部署参考。
- **无障碍基本检查**：`a11y.spec.ts` 包含三项验证——（1）仅用键盘（Tab/输入/Enter）完成登录并进入仪表盘；（2）连续按 Tab 时，焦点可到达所有可交互元素；（3）按 WCAG 相对亮度公式检查对比度，正文文字不低于 4.5:1（1.4.3 正常文字）。**已知限制（Fable 5 M5 复审 H）**：主要按钮的白色文字配主题绿色（#18a058）约为 3.4:1，仅达到 1.4.11 非文字组件的 3:1 下限，尚未达到 AA 文字标准 4.5:1；测试暂以 3:1 为最低门槛，主题色调整列入 v1.x 待办。
- **质量门槛**:后端 ruff/mypy 干净、pytest **371 passed**(+4);前端 eslint/vue-tsc build/vitest 11 绿;Playwright 全套(现有 26 + 新增 a11y 3 / 全旅程 1 / 页面加载 1)。

### M5 里程碑复审(Fable 5,2026-07-11)与修正
M5 完成后由 Fable 5 做独立技术审查,判决「**有条件可发行**」:核心(备份数据路径、导出正确性、调度时区)健全,裂缝集中在队列互踩与发行流程未演练。以下 A/B/D/E/F 已修(各附回归测试 `tests/test_m5_hardening.py`),H 诚实化,C 待用户决定公开时机一起走。

- **A(已修)——单一队列阻塞式分派任务互踩,超时的恢复仍会晚点偷跑**:排课占住单一 worker 时,恢复排在后面;api 超时回失败,worker 空下来后却仍执行恢复→数据库被无预警覆盖。修:`queue._run_blocking`/`render_export` 超时后 `job.cancel()`(不留在队列里等待跑);`queue.solver_busy()` 检测排课进行/排队中,`backups._restore` 在恢复前检查,进行中回 **409「排课进行中,请待排课完成后再恢复」**。分出 ops 队列 + 第二 worker 进程为更完整解,但会引入进程/容器/内存(4GB 预算)复杂度,列 Backlog 专卡处理;A 的数据安全洞已由 cancel + 409 封死。
- **B(已修)——每日备份链一次失败即永久静默断裂**:`daily_backup_job` 先备份再安排下一次,任一次失败→抛出异常→下次永不入队→自动备份无声停止。修:`daily_backup_job` 改为在 try/finally 的 finally 中先安排下一次;`scheduler.heartbeat` 同样修改,并增加自愈——每小时检查 `DAILY_BACKUP_JOB_ID` 不在 `ScheduledJobRegistry` 时就补充调度。
- **D(已修)——`:latest` 对 ARM 用户是地雷**:main push 只建 amd64 却覆盖 `:latest`,ARM NAS(`IMAGE_TAG=latest`)pull 到无 arm64 manifest 会起不来。修:CI `images` job 以 channel 区分——main push 推 `:main`,`:latest` 只在版本标签(双架构)时更新。
- **E(已修)——pg_restore exit 1 的忽略范围过宽、警告未显示在 UI**:exit 1 包括任何被忽略的错误,某张表 COPY 失败也是 exit 1,只凭 returncode 会把数据缺失报告为成功。修:`backup._classify_restore_stderr` 采用白名单——只忽略「无法识别设置参数」(跨版本 GUC),其余 `pg_restore: error` 统一视为失败(presafe 在,可回退);可忽略警告经 `RestoreResult.warnings` 返回,前端 `System.vue` 以对话框显示给管理员(不再只写日志)。
- **F(已修)——session_epoch 持久化可靠性**:Redis 默认 RDB 条件下这个单一 SET 可能一小时未写入磁盘,恢复后 Redis 崩溃→epoch 遗失→旧 cookie 重新生效。修:`force_logout_all` 设置 key 后补 `bgsave()`(尽力而为,失败不阻断主流程)。
- **H(已诚实化)——a11y 对比主张过度**:主色按钮实为文字(适用 4.5:1)却套了 3:1 非文字门槛。已在 `a11y.spec.ts` 与上方补遗如实标注「达 3:1、未达 AA 文字 4.5:1」;主题色调整列 Backlog。
- **C（待处理，发布流程阻塞项）**：仓库为私有时，`raw.githubusercontent` 匿名访问返回 404；GHCR 镜像为私有时，`sudo docker compose pull` 会被拒绝；`IMAGE_TAG=v1.0.0` 依赖的版本标签尚未推送，双架构 ARM64 构建也未验证。因此，“在全新虚拟机上从零拉取并安装”尚未完成实测。处理方式：发布前将仓库和 GHCR 调整为公开，先发布 `v1.0.0-rc1` 演练双架构构建与全新安装，再发布 `v1.0.0`。公开时机由项目负责人决定。
- **v1.x 可延(Fable 5 判定合理,不阻挡发行)**:G(恢复溯源 append-only log、stale 提示持久化;presafe 文件名时戳现已足够)、以及现有 Backlog。

**修正后质量门槛**:pytest **392 passed**(+21,含 test_m5_hardening 12)、ruff/mypy 干净;前端 eslint/vue-tsc build/vitest 绿;Playwright 全套回归;docker 实测 A(排课中恢复被 409 挡)、B(备份失败链仍存活)。M5 里程碑完成,**有条件可发行**(待清 C)。

### 最终发行前总体检(Fable 5,2026-07-12)与修正
公开发行 v1.0.0 前,Fable 5 做全系统(非逐卡)总体检。**核心健全**:逐一核对每个 API 端点的 RBAC——管理类全由 viewer/editor/admin_only 守住,教师类全部限缩本人(`_get_leave`、`_get_own_notification`、`substitution-stats/mine` 忽略用户端 teacher_id),跨学期写入有 `semester_id` 校验,**无 IDOR 洞**;无 SQL 注入面(全 ORM)、无 v-html/XSS;正式 compose 只对外 80/443;`.env` 不进镜像;15 个迁移 downgrade 全部有实现(可逆)。判「有条件可发行」——裂缝集中在「交给非信息背景教师自架时的安全默认」。发行阻挡 A/B/C + F 已修(回归测试 `tests/test_config_hardening.py` 9 个):
- **A(SECRET_KEY 默认无防呆)**:`config.py` 加 `_harden` 验证器——secret_key 落在不安全值集合(`dev-insecure-change-me`/`please-change-this-...`/空)即以 `secrets.token_hex(32)` 取代并 `logger.warning`。避免以公开密钥签署 session。
- **B(HTTPS 部署 cookie 未带 Secure)**:`site_address` 为真实域名且未显式设 `cookie_secure` → 自动 True;`docker-compose.yml` 把 `SITE_ADDRESS` 也传给 api;`.env.example` 补 `COOKIE_SECURE` 说明。
- **C(无请求体上限→单校 OOM)**:Caddyfile 加 `request_body { max_size 200MB }`(容得下真实 .dump 恢复与 Excel 导入);`backup.md` 注明超大 DB 恢复改用 volume 复制法。相关端点均需 editor/admin,属内部误操作等级。
- **F(第三方授权说明)**:新增 `THIRD-PARTY-NOTICES.md`(psycopg=LGPL、poppler/pdftoppm=GPL 子进程、Noto CJK=OFL,均动态依赖/子进程使用,MIT 兼容),README 链接。
- D/E/G 列 v1.x(下方 Backlog)。

---

## M6 v1.1 加固(Fable 5 开卡,2026-07-13;范围与取舍理由见 docs/roadmap.md)

目标:2026 年 8 月排课季前发布 v1.1。依序做,M6-2 先定容器架构,后面的文件与 E2E 叠在其上。
CI 已含 e2e job(30 tests),每张卡完成后 push 即有全栈回归把关;仍须遵守现有 DoD(含真 PostgreSQL 实测与截图目视)。

### [x] M6-1 E2E/测试硬编日期动态化(死线:2026-11 前)
- **描述**:多处测试硬编码未来日期,真实日期超过这些值后 `clock.is_past_slot` 会拒绝代课指派,CI 将无提示地失败。已知:`frontend/e2e/substitution-stats.spec.ts`(`DAY='2026-11-11'`)、`full-journey.spec.ts`、`backend/tests/test_full_flow.py`(`_SEM_START=2026-09-01`、`_SEM_END=2027-01-31`)等;开始处理前先扫描整个项目(grep `2026-`/`2027-`)。改为以「执行当日」推算:请假日=下一个周三(或其他固定星期),学期起止=今天前后推(起=今天往前一个月、结束=往后六个月等),集中成 helper(前端 `e2e/helpers.ts`、后端 conftest 或 fixtures)供各 spec 共用。
- **验收标准**:
  1. 整个项目不存在「会过期」的硬编码日期(作息时间表等与日历无关的常量不在此列)
  2. 日期 helper 有单元测试(含「今天就是周三」边界)
  3. 全套 pytest 与 e2e 绿
- **测试方式**:pytest + Playwright 全套;人工查看 grep 结果确认无漏网
- **实现后(commit 待补)**:两支 helper——`backend/tests/dates.py` 与 `frontend/e2e/dates.ts`(同一套规则),由「执行当日」推算出一个**基准周**(距今 ≥14 天:确保基准周每一节都还没上过,不受执行时刻影响)。范围比卡上预估大:后端 8 个测试档、前端 9 支 spec 全数改用 helper 常量。
- **基准周必须「当周到下周三同月」——这是硬需求,不是美观**:代课推荐的公平计数与月结统计都以「受影响节次那一天的月份」为范围(`_monthly_sub_counts` 用 `affected.date.replace(day=1)`)。第一版 helper 只保证「距今 ≥14 天」,今天(2026-07-14)推出来的基准周刚好是 WED=7/29、WED2=8/5 **跨月**,于是 `test_fewer_monthly_sub_periods_ranks_higher`(林师本月已代 1 节、陈师 0 节)与 `test_cancelling_leave_keeps_already_taught_period` 当场翻车——**动态化第一天就抓到自己的设计缺陷**。修正:`base_monday()` 往后找到「周一 +9 天仍同月」的那一周;跨月案例改由 `cross_month_wednesday()`(相邻两个周三分属前后月)专门负责,月结拆账测试仍验得到。
- **顺手修掉一个假 fallback**:`full-journey.spec.ts` 的 `leaveDay || '2026-11-11'` 是死路径(两边同值),真正该做的是「请假日跟着该单元格的星期走」,已改为 `dayOfBaseWeek(entry.weekday)`。
- **`manual-shots.spec.ts`(手册截图生成器,非回归)**:改为向示范站查学期,取「学期内、今日之后的第一个周三」;学期已过期则明确报错要求重建示范数据,不再静默产出错的图。
- **验证**:pytest **452 绿**(+59,含 helper 的参数化单元测试:每种「今天」落点、跨年、闰年、以及「不论今天是哪一天,WED/WED2 都同月」40 组)、ruff/mypy 干净;前端 eslint/vue-tsc/vitest 绿;干净全栈(schedci,:8090)e2e **30/30 绿**;截图目视确认 UI 显示的是动态算出的「2026-08-05(周三)」而非硬编日期。

### [x] M6-2 后台任务队列拆分(default / ops)
- **描述**:单一 RQ worker 循序执行,排课(可达数分钟)期间导出/备份超时失败(M5 复审 A 的正解)。拆 `ops` 队列:导出(`render_export`)、备份/恢复(`_run_blocking`)、email 改走 `ops`;自动排课独走 `default`。同一 worker 镜像加第二个容器(如 `worker-ops`,`command` 带队列名;`app/workers/worker.py` 支持指定队列)。**数据安全语义不变**:排课中恢复仍须 409(恢复覆盖整个 DB,与排课写回互斥),`solver_busy()` 只看 `default` 队列即可;每日备份调度器要决定归属(建议 ops)。更新 `docker-compose.yml`(5→6 容器)、`docker-compose.limits.yml`(worker-ops 建议 512M,总和仍 ≤4GB)、部署/升级文件(docs/deploy/)、CONTRIBUTING 架构描述。
- **验收标准**:
  1. 真实 60 班自动排课进行中,导出 Excel/PNG 与「立即备份」数秒内成功(docker 实测)
  2. 排课进行中恢复仍返回 409 拒绝(现有测试不退步)
  3. 排课中 worker-ops 被 kill,导出回明确错误而非无声卡死;重启后恢复
  4. limits compose 全栈跑 M5-4 旅程无 OOMKilled
- **测试方式**:pytest(队列路由单元测试)+ docker 全栈实测(排课中导出/备份/恢复)+ e2e 全套
- **实现后**:`queue.py` 分出 `default`(只跑 `run_auto_schedule`)与 `ops`(导出 `render_export`、备份/恢复 `_run_blocking`、发送邮件 `enqueue_email`);`worker.py` 收队列名参数(`python -m app.workers.worker [ops]`),entrypoint `worker` 角色把余下参数透传;compose 新增 `worker-ops`(同一 worker 镜像,`command: ["worker","ops"]`),5→6 容器。
- **调度器改挂 ops worker**:定时任务(每日备份、心跳)都是运维工作,排进 `ops` 并由 `worker-ops` 以 `with_scheduler=True` 取出执行。排课 worker 不运行调度器——**一次求解可能持续数分钟,不适合负责需要准时执行的任务**。
- **升级路径的隐形问题**:M6-2 之前每日备份排在 `default` 的 ScheduledJobRegistry。调度器改为监听 `ops` 后,旧任务将不再被取出——**每日备份会在升级当天静默中断**(备份最不能接受的失败模式)。`_drop_legacy_default_schedules()` 在 ops worker 启动时按固定 job_id 精确移除旧调度再重新安排(不影响其他 job),并附回归测试。
- **`solver_busy()` 的 409 保留,但理由改写**:分队列后恢复不再「排在排课后面」,可是仍必须挡——**这是数据安全不是排队**:pg_restore 覆盖整个数据库,而排课 worker 正要把结果写回同一个库。
- **验证(docker 全栈,六容器 + limits 3.7GB)**:60 班自动排课**进行中**调用运维端点——① 导出 Excel **0.0s**、② 导出 PNG(ops worker WeasyPrint 渲染)**4.0s**、③ 立即备份(ops worker pg_dump)**0.5s**、④ 恢复返回 **409** 拒绝;排课全程 `running` 未被打断。**旧架构下 ①②③ 会排在排课后面直到超时失败——这就是这张卡的全部意义。** 另验 ops worker 停止:导出/备份返回明确 **502**(「背景忙碌或超时」,90s/120s 上限后),而非无提示地卡住;重启后 3.6s 恢复。limits 下运行全套 e2e 30/30 通过,六容器 OOMKilled 全 false、Restarts 全 0(worker-ops 峰值远低于 512MB 上限)。
- **质量门槛**：pytest 463（新增 11 项 `test_queue_split.py`）、Ruff/Mypy 通过；前端 ESLint、vue-tsc、Vitest 通过；`sudo docker compose config` 与 limits 叠加配置均通过。
- **文件**:`docs/architecture.md` 新增 **D9 队列分工**(含容器图改绘)、`deploy/README`、`install`、`upgrade`(**显著警语:v1.1 多一个容器,只换镜像不换 compose 会让导出/备份/发送邮件全部超时失败**)、`faq`(新增「导出一直失败怎么查」)、`README`、`CONTRIBUTING`(新增后台任务该走哪条队列的准则)。

### [x] M6-3 部分排课三合一(排不下的课不再炸整锅)
- **描述**:(a) `model_builder` 对候选为空的课直接 raise `SolverInputError`,整个部分排课失败——改为部分排课模式下建模前把该课移入未排列表,其余正常;非部分排课保持 raise(信息要写入 log,同时修复 Backlog 中「check_feasibility 丢失信息」的问题)。(b) 未排列表目前只保存在 Redis 24h(`progress.py` TTL),草稿被 force 发布后就没有任何记录——改为随结果草稿持久化(建议 timetables 增加 JSON 字段或子表,Alembic 迁移),版本页与发布警告都改为读取持久来源。(c) `_unscheduled()` 按 assignment 逐项记录,走班群组少排一个时段会记 N 项——按排课单位去重,「未排 N 节」不再重复计数。
- **验收标准**:
  1. 一门完全没有可排位置的课(如未放宽 H4 的协同教学)→ 部分排课成功,该课列入未排列表并注明原因
  2. Redis 清空后,草稿的未排列表仍可查;force 发布后版本页可见「发布时未排 N 节」
  3. 走班群组掉 1 格只记 1 项(单元测试)
  4. validator 全套与现有 solver 测试不退步
- **测试方式**:pytest(solver + API)+ 真 PostgreSQL 实测 + e2e auto-schedule spec 扩充
- **实现后(2026-07-14)**:
  - **(a) 完全排不下的课不再炸整锅**:`_make_lesson_vars` 对候选为空的 lesson,**只在部分排课模式下**改为 `_force_drop()`(建一个恒为 1 的 drop 变量,不建 x/pos 变量),列入未排列表并带上原因;一般模式保持 raise。部分排课的承诺就是「排不下的列列表、其他照排」,先前却在最需要它的时候整锅失败。
  - **(b) 未排列表持久化**:`timetables.unscheduled` JSONB(迁移 0016,真 PG 验过 upgrade/downgrade 可逆),由 `write_result` 随结果草稿写入。**但 Backlog 的描述与现状不符,已据实修正**:「哪些课没排」其实一直查得到——`completeness()` 从 DB 重算(教学任务应排节数 vs 已排单元格),对草稿与已发布课表均可,不依赖 Redis。真正只活在 Redis 24h 的是**排不下的原因**(只有建模当下的 solver 知道)。故设计为:未排列表仍以 DB 推导为唯一真相(连手动改过的课表都算得对),持久化的 solver 记录只补上「为什么」——`completeness()` 的每条 `unplaced` 多一个 `reason` 栏。
  - **(c) 走班群组不重复计数**:`extract()` 的未排节数改以**排课单位**计数(先前按 assignment 逐项记录)。同时发现群组的 `subject_name` 只显示第一门选修会造成误解(一个群组是「多门选修同时段开」),改为列出所有科目(「选修A、选修B」)。
  - **同时修复**:`check_feasibility` 丢失 `SolverInputError` 信息 → 改为记录 log(否则未来任何建模 bug 都会被误报为「这份数据无解」)。Backlog 该项结案。
- **验证**:pytest **468**(+5,`tests/solver/test_partial_hardening.py`)、ruff/mypy 干净;前端 eslint/vue-tsc/vitest 绿;迁移 0016 对真 PostgreSQL upgrade→downgrade→upgrade 全过;e2e **31/31**(新增 `partial-unscheduled.spec.ts`),**截图目视确认**自排页未排表列出「美术 · 找不到任何可排的 1 连堂时段」、版本页发布警告的「原因」栏同样显示该句,且 force 发布后 `completeness` 仍查得到。

### [x] M6-4 开新学期复制补全(起止日 + constraint_config)
- **描述**:`semester_copy.py` 不带学期起止日与 `constraint_config`(软约束权重回默认),新学期忘补起止日会让「今日」判定全错。复制对话框加起止日字段(必填,默认带「上学期 +半年」推算值);`constraint_config` 随复制带过去。
- **验收标准**:
  1. 复制后新学期有正确起止日与相同软约束权重(真 PG 实测)
  2. 前端对话框有起止日字段与默认值
  3. e2e copy-semester spec 扩充验证
- **测试方式**:pytest + e2e
- **实现后(2026-07-14)**:`SemesterCopyRequest` 加 `start_date`/`end_date`(pydantic 验证结束不早于开始 → 422)与 `constraint_config: bool = True`;`copy_semester()` 以 keyword-only 收起止日,并复制 `constraint_configs` 各列。**起止日刻意不沿用来源**(那是上学期的日期),由调用方明确给。前端复制对话框新增起止日 date-picker,默认值为**来源学期往后推半年**(`halfYearLater()`),并在下方提示「请确认实际校历后修改」;起止日未填时「创建新学期」停用(漏填不会报错,但请假展开、今日看板、代课「已上过」判定会整个算错,而页面上看不出来)。复制项目多一个「排课偏好设置」勾选——先前新学期会**悄悄**回到默认权重,上学期调好的偏好就白调了。
- **验证**:pytest **472**(+4:起止日写入、颠倒日期 422、偏好跟着复制、明确不勾选时回默认)、ruff/mypy 干净;前端 eslint/vue-tsc/build/vitest 绿;e2e **31/31**(`copy-semester.spec.ts` 扩充为验起止日默认值 +6 个月、实际写入、偏好设置跟着走),**截图目视确认**对话框带出「2027-03-01 ~ 2027-07-20」。**真 PostgreSQL 实测**:来源设 cap=4/S2=55/S5=30 → 复制后新学期起止 2027-02-15~2027-06-30、偏好完全一致;颠倒日期回 422。

### [x] M6-5 小型加固批量(六小项)
- **描述**:一次出货六个 S 级项目——①班级名称加 `uq(semester_id, name)`(迁移前先清重复,API 撞名回 409);②`/api/docs`/`openapi.json` 默认关闭,`.env` 显式开启(`API_DOCS_ENABLED`,dev compose 带开);③主题主色调深至白字对比 ≥4.5:1(不动整体设计),`a11y.spec.ts` 按钮门槛提到 4.5 并移除「未达 AA」注记;④冲突定位把 `should_stop` 传进 `conflict_explainer` 逐步试解循环,按取消得 cancelled;~~⑤`check_feasibility` 的 `SolverInputError` 信息记 log~~(**M6-3 已修,本卡不必再做**);⑥`substitution-log`/`leaves` 等列表查询加服务器端上限(如 limit≤1000,完整分页留 v1.2)。
- **验收标准**:逐项——重复班名 409 且迁移可从有重复数据的库升级;正式 compose 下 `/api/docs` 404、设置开启后可用;a11y 测试以 4.5 门槛绿;定位中按取消 ≤数秒内回 cancelled;列表超限回截断结果与提示
- **测试方式**:pytest(每项至少一测)+ e2e(a11y、取消路径)+ 真 PG 迁移实测
- **实现后(2026-07-14)**:
  - **① 班名唯一**:`uq(semester_id, name)`(迁移 0017)+ API 创建/改名 409 + **Excel 导入逐行拦截**(文件内重复、与现有班级重复都指出是第几行,不让它撞 DB 约束变成看不懂的错误)。**迁移必须先处理现有重复数据**——有重复班名的学校正是最需要这个约束的人,不能让他们一升级就失败。重复者依 id 保留第一条、其余改名为「301 (2)」…,且**会避开数据库里已存在的同名**;不删任何数据。真 PG 实测最恶劣情况(三个 301 + 一个现有的「301 (2)」)→ 得到 301 / 301 (3) / 301 (4) / 301 (2) / 302,零重复、约束创建、可逆。
  - **② `/api/docs` 默认关闭**:`api_docs_enabled=False`(`docs_url=None` → 路由不存在,404);`.env` 可显式打开,`docker-compose.dev.yml` 带开。端点本身均受权限保护,公开它不是漏洞,但没必要把整套内部 API 摊在网络上(尤其 VPS + 公开域名)。正式栈实测 `/api/docs` → 404。
  - **③ 主色达 AA**:新增 `frontend/src/theme.ts`——Naive 默认 `#18a058` 白字只有 ~3.4:1(那是 1.4.11 非文字组件的门槛,而按钮上的字**就是文字**)。压深到 `#0d7a43`(**5.41:1**),hover `#0e8449`(4.76:1)也达标,色相不动。`a11y.spec.ts` 门槛从权宜的 3:1 提到 **AA 的 4.5:1**,并移除 M5 留下的「未达 AA」诚实说明——现在真的达了。
  - **④ 定位可取消**:`explain()` 接收 `should_stop`,每次试解前检查并抛出 `Cancelled`;solve_job 捕获后把任务标为 **cancelled**(而非 failed)。定位最长运行一分钟,此前完全不检查取消标记——用户单击取消后只能等待,最后还会收到一份已经不需要的报告。
  - **⑥ 列表上限**:`substitution_log.query(limit=MAX_ROWS)` 与 `GET /leaves`(`MAX_LEAVE_ROWS`)各 1000,**下到 SQL 的 `.limit()`**(测试以 limit=1 验证真的生效,不是个没人用的参数)。完整分页 UI 留 v1.2。
- **验证**:pytest **482**(+10,`tests/test_m6_hardening.py`)、ruff/mypy 干净;前端 eslint/vue-tsc/build/vitest 绿;e2e **31/31**;真 PG 迁移实测(含重复数据与可逆);正式栈 `/api/docs` 404;截图目视新主色。
- **E2E 发现一个现有测试脚本缺陷**：`substitutions.spec.ts` 的 `klass()` 看似 get-or-create，实际上每次都执行 POST；`place('王师','语文','701')` 会重复创建“701”班。此前允许重复班名，问题没有暴露；增加唯一约束后立即返回 409。现已改为真正的 get-or-create。`wizard.spec` 曾因此连带失败：前一个用例没有完成清理，残留学期占用了仪表盘默认位置；这是同一问题造成的连锁影响。

### [x] M6-6 复审修正(Fable 5 M6 复审判为「有条件可发行」的两个阻挡项 + 两个顺手项)
- **描述**:A(阻挡)ops 队列无 worker 时 fail-fast;B(阻挡)dev compose 没有任何进程守 ops;C 核心依赖钉主版号上限;D 列表截断提示。
- **验收标准**:停掉 worker-ops 后导出/备份/恢复**立即**回一句说得出处理方式的错误(不是超时);dev compose 起得动导出/备份;依赖装得起来且全测绿;列表取到上限时页面讲明被截断。
- **测试方式**:pytest + vitest + 六容器栈实测(含**实跑一次完整恢复**)
- **实现后(2026-07-14)**:
  - **A**:`ops_worker_available()`(`rq.Worker.count(connection, queue=ops_queue)`)。`render_export` 与 `_run_blocking`(备份/恢复)在**分派任务前**检查,没有 worker 就立刻抛出 `RenderError`/`BackupJobError`,信息直接点名 worker-ops 与 docker-compose.yml。任务分派前的拦截对恢复尤其重要:任务若滞留在队列中,worker 稍后启动会**在没有预警的情况下覆盖数据库**。`enqueue_email` 只记录 `logger.error`,**不抛出异常**——它的调用点在事务 commit 之后,站内通知已送达,不能为了一封邮件让已成功的操作看起来像失败(邮件仍会入队,worker-ops 启动后会补发)。api 启动时另做一次后台检查(等待 6×2 秒,避免 compose 并行启动造成误报)并写入日志。无法判断时(Redis 抖动)**统一放行**——误判成「没有 worker」会拦截本来可以成功的导出,比让它按原流程超时更糟。
  - **原本的升级陷阱比 M6-2 卡上写的更严重**:旧 compose 的 `command: ["worker"]` 在新镜像下不只不守 ops,**也不跑调度器**——每日自动备份是**静默**停摆的(导出超时至少还很吵)。这正是 fail-fast 必须做进 v1.1 的理由:文件警语挡不住没读文件的人。
  - **B**:`docker-compose.dev.yml` 的 worker 改 `command: ["worker", "ops", "default"]`(单进程守两条队列;正式环境才拆两个容器)。先前 dev **完全没有**进程在守 ops,导出、备份、发送邮件、定时任务全失效——repo 已公开,这会是外部贡献者的第一印象。
  - **C**:核心依赖全部钉主版号上限(fastapi/sqlalchemy/redis/rq/pydantic/psycopg/alembic/uvicorn/bcrypt/openpyxl/itsdangerous)。踩过:`redis` 未设上限 → 某次重建装到 redis-py 8 → 导出/备份在新环境统一超时。镜像每次发行重新构建,不钉上限等于「上游哪天发大版,用户的部署自己坏掉」。
  - **D**:`SubstitutionLog` 与 `Leaves` 取到条数上限(1000)时各显示一行截断提示(要看更早的请缩小日期区间/改用调课与代课记录查询)。M6-5 卡上写了「与提示」却只做了截断——不讲的话,排课管理员会以为「这学期就只有这些记录」。
- **验证**：pytest 488（新增 6 项 `test_queue_split.py`）、Ruff/Mypy 通过；前端 ESLint、vue-tsc、构建通过，Vitest 15 项；E2E 31/31。六容器全栈实测：（1）停止 worker-ops 后，导出、备份和恢复均立即返回包含处理建议的 502，且没有分派任务；（2）执行 `sudo docker compose start worker-ops` 后，导出恢复正常并生成 43KB PNG；（3）完整恢复耗时 4.05 秒，自动生成恢复前备份，学期、班级和已发布课表均恢复，旧会话返回 401 并要求重新登录；每日自动备份文件也已按计划生成。

### [x] M6-7 恢复后 log 喷 AdminShutdown traceback(M6-6 实测发现,发行前修掉)
- **描述**:恢复**成功**后,api log 会输出一段 `ERROR: Exception in ASGI application` + `AdminShutdown` traceback。功能完全正常(响应 200、数据正确、后续请求正常),但**刚单击「恢复」的排课管理员正处于最需要确认结果的时刻**——此时查看 log 却看到一段红色错误,很容易误以为恢复失败。这不是数据问题,而是信任问题,不应带入发行版本。
- **根因**:`pg_restore --clean` 会中止数据库上的所有连接,包括本请求**验证身份时**建立的数据库会话(路由本身未声明 `db`,但 `admin_only` → `get_active_user` → `Depends(get_db)` 会建立会话)。FastAPI 0.106 起,yield 依赖的收尾是在**响应发送后**才执行,届时 `db.close()` 通过已经失效的连接发送 ROLLBACK → `AdminShutdown` 变成 ASGI 异常。因为响应早已发送,用户拿到的是正确的 200——只有日志中出现错误。
- **修法**(两层):
  1. **修复根因**:`_restore()` 在分派任务前先 `db.close()`。恢复期间本来就用不到这个数据库会话(审计记录通过新连接写入**恢复后**的数据库)。路由额外声明一个 `db: Session = Depends(get_db)`——FastAPI 对同一个 callable 有请求内缓存,拿到的**就是** `admin_only` 内部使用的会话,不会创建第二个。关闭前先把 `user.id`/`user.username` 取成标量值,避免 `user` 成为 detached instance。
  2. **防线**:`get_db()` 的 `finally` 捕获 `close()` 的异常并记录一条 warning。收尾发生在响应发送后,此时抛出异常只会变成一段没有请求可归属的 traceback;真正的失败会在**查询时**报错,不会被这里掩盖。这道防线也适用于「恢复期间其他用户正在处理的请求」。
- **验证**:pytest **490**(+2:①拦截请求会话,断言 `run_restore` 被调用时它**已经关闭**;②`get_db` 收尾遇上 close 失败时不抛出异常、只记录 warning)、ruff/mypy 干净;e2e **31/31**。**六容器栈实测**:建学期 152/班级 799 → 备份 → 删学期 → 恢复 → **api log 全程零 traceback、零 ERROR**(此前必定输出),响应 200/3.5s、学期与班级恢复、旧 session 401、审计记录通过新连接写入(`admin | 恢复自 …;现状已备份为 …`)。

### [x] M6-8 「系统管理」整页打不开(v1.0.0 起就有,重拍手册截图时抓到)
- **描述**:`/settings/system` 只剩左侧菜单,内容区一片空白——**备份、恢复、SMTP、重设向导四项功能全都点不进去**。`System.vue` 调用 `useDialog()`(M5 复审 fca20ca 加的,用来显示恢复后的可忽略警告),但 `App.vue` 从来没挂 `<n-dialog-provider>`;Naive 会在 setup 直接抛出异常,整页渲染不出来。
- **为什么溜过所有测试**:这一页**没有任何 e2e 覆盖**(31 支 spec 没一支碰它),vitest 也没测。备份/恢复的验证一直是走 API,从没走过 UI。是「重拍手册截图」这件事把它逼出来的——截图生成器截到一张白页面。
- **修法**:`App.vue` 补上 `<n-dialog-provider>`;`seed_e2e` 新增 `e2e_admin` 账号(卡片是 admin-only);新增 `system-settings.spec.ts`——三张卡片渲染 + 立即备份(真的打到 worker-ops 的 pg_dump)+ 删除备份。第一个断言就是核心:页面只要 setup 抛出异常就是全白,必红。
- **验证**:pytest **490**、vitest 15、e2e **32/32**(+1)、ruff/mypy/eslint/vue-tsc 干净;**截图目视**系统管理页三张卡片完整。

### [x] M6-9 操作手册 10 张截图重拍 + 截图生成器自备示范数据
- **描述**:M6-5 把主色调深后,手册的 10 张截图全成了旧主色;且截图生成器 `manual-shots.spec.ts` 依赖一台「已经灌好示范数据」的测试站——那些数据当初是手动灌的、没留脚本,导致要重拍时没人知道当初的数据长什么样。
- **修法**：示范数据使用公历学年（8 位教师、701~703 班、24 项教学任务），与首次登录改密一并收进 spec；脚本可重复执行，并从空数据库生成 10 张截图。
- **验证**：`sudo docker compose -p manual up -d`（空数据库）→ `E2E_BASE_URL=... npm run e2e:manual` → 生成 10 张新截图，并逐张确认主题色、真实数据、课时统计、代课记录和系统管理页面。

### [x] M6-10 首次登录修改密码页回归测试
- **描述**：补齐 `/change-password` 的端到端覆盖，并修复按钮点击和表单提交同时触发导致一次操作发送两次请求的问题。提交中禁止再次触发，键盘回车仍走同一表单提交路径。
- **验证**：覆盖首次登录跳转、修改前接口限制、输入校验、成功离开页面、新密码重新登录，以及单次操作只发送一次请求。

## M7 v1.2 易用性与国内适配(2026-08-02)

### [x] M7-1 一键安装与可复现镜像
- **描述**：新增 Windows PowerShell 与 Linux/macOS/NAS 安装脚本，支持安装目录、端口、Compose 项目名称、镜像版本和仅生成配置；避免误接管其他目录的同名部署。Web 镜像使用锁文件和 `npm ci`，跨架构构建固定在原生构建平台。

### [x] M7-2 国内初中示例数据（后续已撤回）
- **描述**：全新系统可从向导或系统管理加载虚构的“海州市启明实验初级中学”，包含 18 个班、49 位教师、16 个科目、252 条教学任务和每周 594 课时。课程、班级、职务、作息和时区均采用国内通用表达；所有数值仅供功能演示，不代表政策标准。
- **安全边界**：系统存在任何学期后即关闭入口并拒绝接口请求，避免污染正式数据；加载完成后自动完成设置向导。
- **后续决策**：该能力在尚未部署时由 ADR-0006 移除；本条仅保留开发历史，不再描述当前产品能力。

### [x] M7-3 学校信息与超课时上限
- **描述**：学校名称改为系统管理内可修改，并统一用于课表、导出和通知。系统管理员可设置允许的超课时上限，教学任务创建、修改与 Excel 导入使用同一校验；未维护基本课时的教师不执行限制。

### [x] M7-4 离线文档与文档同步检查
- **描述**：部署与开发 Markdown 文档可生成离线 HTML，包含目录、深浅色模式和窄屏布局。CI 检查迁移是否同步更新架构文档，并检查生成文件与 Markdown 是否一致。

### [x] M7-5 操作审计服务器端分页与共享分页基础
- **描述**：系统管理 / 安全追溯 / 操作审计改为服务器端分页，按 `created_at DESC, id DESC` 稳定排序；提供精确总数、页码、20/50/100 条、快速跳页、400ms 搜索防抖、回车立即搜索、刷新和独立错误重试。分页、页容量和查询词写入 URL，深链进入时自动定位审计区域；过期响应不覆盖新结果，错误保留最后一次成功数据，越界页自动回到末页。
- **搜索语义**：空白分词后各词 AND；每个词可命中操作者、角色、动作、目标、版本、编号、结果、原因或说明。内部代码与页面上的简体中文标签均可搜索，查询在服务器端、大小写不敏感。
- **复用边界**：后端共享 `PageParams` / `Page[T]` 契约，前端共享 `useServerPagination` 状态协调器与 `PagedListControls` 控件；各页面的筛选、排序和 SQL 保留在所属业务模块，不增加通用 SQLAlchemy 查询助手。
- **后续页面清单**：
  - [x] 操作审计。
  - [ ] 请假记录(`/leaves`)。
  - [ ] 代课日志(`/substitution-log`)。
  - 其他列表仅在数据规模或使用反馈证明需要时加入。
- **验证**：SQLite API 测试覆盖精确总数、稳定排序、中英文多词搜索、参数校验与越界页；Vitest 覆盖 URL 状态、并发丢弃、错误保留与搜索防抖；Playwright 以桌面和 390px 窄屏覆盖深链、翻页、快速跳页、页容量和搜索。PostgreSQL 16 迁移以 `CREATE INDEX CONCURRENTLY` 建排序/筛选索引并启用 `pg_trgm`；100 万条临时数据基准最慢场景 595.9ms，低于 1 秒门槛，临时数据不写入真实审计表且不进入 CI。

---

## 测试策略总则

1. **三套学制验证数据集**(`backend/tests/fixtures/`,M1 期间创建,整个项目共用):
   - `elementary_small`:小学 6 班(包班+任课教师+周三下午空+班主任时间)
   - `junior_high_mid`:初中 12 班(学科课程+弹性课程+兼行政减课教师)
   - `vocational_high`:中职 15 班 3 科(3 连堂实习+实训室容量限制+企业兼职教师限定时段+走班)
2. **排课引擎双重验证**:所有 solver 测试以独立 `validator.py` 逐项检查硬约束,绝不以 solver 自身状态为准;validator 同时用于「导入外部课表检查冲突」功能的基础。
3. **测试金字塔**:pytest 单元(服务层/引擎)为主体;Vitest 覆盖 TimetableGrid 等核心组件;Playwright 仅覆盖六大关键旅程(登录、向导、手排、自排、调课与代课、导出)。
4. **每张任务卡的完成定义(DoD)**:功能实现 + 卡上验收标准自验通过 + 新增测试绿灯 + 现有测试不退步 + ruff/eslint 干净。

---

## 给开发 AI 的固定工作准则

1. 开工前先读 `docs/architecture.md` 对应章节;规格冲突时以 architecture.md 为准并反馈矛盾。
2. 一次只做一张卡;卡外的好点子记入本文件末尾「Backlog」区,不顺手实现。
3. UI 文案统一使用自然简体中文和全国中小学通用教务用语。
4. 数据库 schema 变更必附 Alembic 迁移,且可从前一版顺向升级。
5. 完成后更新本文件复选框为 `[x]`,并在 PR/报告中逐条对照验收标准说明验证方式与结果。
6. **由 AI 使用 Playwright 直接执行 UI 验收**（自 2026-07-09 起已获用户授权）：为包含界面的任务编写验收脚本，以 headed 和 slowMo 模式在屏幕上执行，将关键步骤截图保存到 `frontend/e2e/screenshots/`，检查截图后向用户报告。脚本保留在 `frontend/e2e/` 中，逐步形成回归测试。用户只需观察并反馈交互与文案，无需手动重复操作。

## Backlog(开发中冒出的点子记这里,不调度)

- 【Fable 5 总体检 D】CORS `cors_origins` 内置 localhost 且不可由 .env 设置;同源部署下无害,v1.x 改为可设置并于正式部署收敛。
- 【Fable 5 总体检 E】列表查询未分页 → **操作审计已于 M7-5 完成服务器端分页**；`leaves` 与 `substitution-log` 仍保留 M6-5 的 1000 条服务器上限，并作为后续分页清单中的两项明确待办。
- ~~【Fable 5 总体检 G】`/api/docs` 与 openapi 在正式环境公开~~ **已于 M6-5 修毕(2026-07-14)**:默认关闭(404),`.env` 的 `API_DOCS_ENABLED` 可显式打开,dev compose 带开。
- 【Fable 5 总体检 C 后续】`restore-upload` 目前使用 `await file.read()` 把整个文件读入内存;v1.x 改为流式写入,避免大备份占满 api 内存(现以 Caddy 200MB 上限 + 超大 DB 使用 volume 复制方式缓解)。
- 【Fable 5 M5 复审 A 正解】后台任务分 `default`(排课)/`ops`(导出/备份/恢复)两队列 + 第二个 worker 进程,让快慢任务隔离——目前排课占住单一 worker 时,排课管理员导出课表会超时失败(已由 cancel-on-timeout + 恢复前 409 封死数据安全洞,但导出体验仍受影响)。需评估进程管理、4GB 内存预算与部署文件(5→6 容器或单容器双进程)。
- ~~【Fable 5 M5 复审 H】主题主色 `#18a058` 白字按钮对比仅 ~3.4:1~~ **已于 M6-5 修毕**:主色压深至 `#0d7a43`(5.41:1),a11y 测试门槛提到 AA 的 4.5:1。
- 【Fable 5 M5 复审 G】恢复溯源:`backup_dir` 加 append-only `restore.log`(谁于何时恢复哪份),因目前审计写进恢复后 DB 有溯源断点(presafe 文件名时戳暂可佐证);条件 D 的 stale 警告改为今日看板持久徽章而非一闪即逝的 toast。
- 前端 bundle 偏大(~1.4MB,主因 `app.use(naive)` 全量注册 Naive UI)。M2 课表页完成后改为按组件 import 或用 `naive-ui/es` 自动导入,缩小体积。
- ~~M0-3 CI 尚未加入 Playwright E2E~~ **已完成（2026-07-13，Fable 5）**：CI 增加 `e2e` 任务，在 runner 上使用 buildx 构建三个镜像，执行 `sudo docker compose up -d --wait` 启动全栈，通过 `python -m app.scripts.seed_e2e` 幂等创建测试账号并完成向导状态，然后运行 Playwright Chromium 项目。失败时上传报告、trace、截图和容器日志；镜像发布任务依赖 E2E，回归失败时不会发布镜像。本机使用全新栈验证 30/30 通过。CI 首次运行还发现了 redis-py 8 下 RQ 阻塞读取与并发共享客户端导致的超时问题；现已改为每 0.5 秒轮询 XREVRANGE，不再依赖阻塞客户端唤醒。
- ~~前端 CI 用 `npm install`(未提交 package-lock.json)~~ **描述已过时,顺手处理(2026-07-13)**:lock 文件其实早已入库;CI 的 frontend 与 e2e job 改用 `npm ci` + npm 缓存(以 `npm ci --dry-run` 验证 lock 与 package.json 同步)。
- ~~Compose 端到端冒烟测试尚未纳入 CI~~ **已由 E2E 任务覆盖（2026-07-13）**：该任务会执行 `sudo docker compose up` 启动全栈，等待健康检查，并运行真实用户流程。
- **企业通讯平台通知适配器（v2）**：根据试用学校的实际平台，通过 webhook 对接企业微信、钉钉等服务，并作为新的 `NotificationChannel` 实现。现有 `teachers.line_id` 字段仅作为通用即时通讯账号保存，以保持数据接口稳定。
- ~~开新学期复制目前不带学期起止日~~ **已于 M6-4 修毕(2026-07-14)**:复制对话框加起止日字段(必填,默认带来源 +半年)。
- ~~班级名称同学期无唯一性约束(可建两个「301」)~~ **已于 M6-5 修复**:`uq(semester_id, name)`(迁移 0017,会先为现有重复数据改名)+ API/导入拦截。
- **走班群组内教学任务的 `periods_per_week` 未强制一致**(M3-0 发现):群组是「同时段开课」,`placements_for` 一次放入全部成员教学任务,节数不一致时课时较少的一项会先被 H8 周节数守恒拦截,语义不明确。`class_loads` 已取群组内最长者计算班级占用;M3-2 的 pre-flight 已加 `group_shape_mismatch` 错误、建模则直接拒绝。仍建议在教学任务创建/修改的 API 中直接拦截(409),让用户当场知道。
- **镜像因 ortools 膨胀到 660MB**(M3-2):ortools 连带拉进 numpy/pandas/protobuf。实际只有 worker 容器需要排课引擎,api 容器不需要。可拆成两个镜像(共用 base + worker 额外装 ortools),或改用 `ortools` 的精简发行版。部署频宽敏感时再处理。
- ~~**开新学期复制不带 `constraint_config`**(M3-3)~~ **已于 M6-4 修毕**:复制对话框加「排课偏好设置」勾选(默认带)。
- **软约束权重设置 UI**(M3-3,v2):目前只有 `GET/PUT /api/solver/config`,没有页面。等 M3-4 的自动排课页上线后,把权重滑杆放在该页的「高级设置」折叠区。
- **科目 Excel 导入没有「主科」栏**(M3-3):`subjects.is_major` 只能在科目表单勾选。导入模板可加一个选填栏。
- **一门课整学期固定一间教室**(M3-2 建模选择):`y[教学任务, 教室]` 是每项教学任务一个变量,而非逐格选择教室。符合实际使用习惯(课表上一门课固定在一间教室),变量数量也小得多。若日后需要「同一门课不同节在不同教室」,改为 `y[教学任务, 节次, 教室]` 即可,约束式不变。
- `teacher_time_rule` 无作息时间表维度(M2 检查 2026-07-10):(weekday, period_no) 的墙钟意义随班级作息时间表浮动,多表学校中同一条规则在初中部与高中部指到不同时间。v1 确定:规则以「该项教学任务所属班级的作息时间表」解读(现行 conflict_checker 行为,M3-2 建模比照,单表学校无此问题);日后如有跨表教师的实际需求,再改为墙钟区间定义(schema 需加 period_table_id 或改存时间区间)。
- ~~【Fable 5 审查】部分排课宣称「永远有解」,但 `_make_lesson_vars` 在候选为空时先 raise~~ **已于 M6-3 修毕(2026-07-14)**:部分排课模式改为 `_force_drop` 列入未排列表并注明原因;一般模式保持 raise。
- ~~【Fable 5 审查】走班群组在部分排课少排一个时段时,「未排 N 节」会重复计数数倍~~ **已于 M6-3 修复**:未排节数改以排课单位计数。
- ~~【Fable 5 审查】冲突定位期间(最长 60 秒)不检查 `should_stop`~~ **已于 M6-5 修毕**:每次试解前检查,取消得 cancelled。
- 【Fable 5 审查】`check_feasibility` 丢失 `SolverInputError` 的信息:未来任何建模 bug 都会被误报为「数据无解」。至少把原始信息记录到 log / conflict detail。
- 【Fable 5 审查】`test_purity.py` 只收 `level == 0` 的 import,相对导入(`from ..models import ...`)可完全绕过纯度扫描。
- ~~【Fable 5 审查】未排列表只活在 Redis(24h TTL)~~ **已于 M6-3 处理,但叙述须更正(2026-07-14)**:「哪些课没排」其实一直查得到——`completeness()` 从 DB 重算,对草稿与已发布课表均可。真正会遗失的是**排不下的原因**(只有 solver 知道),已随草稿存进 `timetables.unscheduled`(迁移 0016)并在完整性报告中呈现。
- 【Fable 5 审查】「validator/report 与 model_builder 零共用代码」严格说不成立:三者共用 `problem.py` 的 `slots_overlap`(D7 判定)与 `course_key`(排课单位语义)。独立性涵盖**约束编码**,不涵盖这两个定义层谓词。应为它们补直接的边界单元测试。
- 求解前先跑一次 hard-only 可行性探测(约 1 秒):既能提早报告「这份数据无解」,又能把该解当成正式求解的 warm start。目前是在失败之后才探测。
- 部分排课的 timeout 几乎必定用满:CP-SAT 找到最佳的「未排 2 节」很快,但要证明「不可能只少排 1 节」很慢。可考虑找到解后以未排节数为上界再收敛,或给部分排课独立的较短默认时限。
- 冲突定位的旋钮列表未含「班级可排节次」与「连堂结构」;`structural` 模式目前只列最吃紧的班级/教师,没有具体到「哪一门课改成连堂就好」。
- ~~【E2E 进入 CI 后的定时问题,2026-07-13 发现】多支 e2e spec 硬编码未来日期~~ **已于 M6-1 修复(2026-07-14)**:前后端各一支 `dates` helper 由执行当日推算基准周,整个项目的 17 个测试文件均已改用;问题已消除。

---

## M3 审查修正(Fable 5 独立审查,2026-07-10)

M3 完成后由 Fable 5 做独立技术审查,判决「有条件可进 M4」。以下 5 项已修:

- **A. H10 双轨判定**:`conflict_checker` 写死 `cap=2`,solver 却读 `constraint_config`。学校把上限设成 3,自动排课排得出来、手动拖拽却报违规。改为由 `check_conflict` 读学期设置(hot path 加一次查询,p95 仍 <100ms)。**M4 调课与代课直接重用这支检查器,这条裂缝必须先补。**
- **B. 软约束权重无上限**:`PUT /solver/config` 接受 `{"S2": 20000}`,而部分排课的「整节不排入」惩罚是 10000 → solver 会理性地丢课换分散度。新增 `MAX_WEIGHT = 100`(API 挡、`load_config` 读取时夹),并在 `Relaxation.__post_init__` 断言量级顺序。
- **C. `unknown` 静默降级**:试解超时回 `unknown` 时被当成「不可行」,但 `complete` 没有跟着降,`structural` 于是宣称「即使放宽所有可调整的项目仍然无解」——一句从未被证明的话。新增 `_Prober` 追踪 `certain`,任何 `unknown` 都让 `complete=False`,structural 措辞随之收敛。
- **D. pre-flight 教室/场地供给不看科目适用性**:唯一的专用教室绑「美术」,音乐课要求专用教室 → 检查放行、建模必然失败、定位找不到该教室/场地、报告文不对题。改为依「候选教室/场地集合」分组比对供需(与 `_candidate_rooms` 同义),新增 `room_no_candidate` 结构性错误(部分排课亦挡)。
- **E. `_room_numbers` 混用池需求与单间供给**:多间同类型教室时,原因卡会凭空放大缺口。改为整池计算并在信息中列出教室名。

验证:pytest 273(+11,含 unknown 路径 4 个测试)、真实 PostgreSQL 打过 A/B/D 端点、e2e 16 绿。
