# 第三方组件与授权 Third-Party Notices

本项目(学校排课、调课与代课管理系统)以 **MIT** 授权释出。系统运行时会用到下列第三方组件。这些组件均以**独立函数库**(动态依赖)或**独立程序**(子进程调用)的形式使用,不会将其授权条款加诸于本项目的源代码——因此与本项目的 MIT 授权兼容,可自由散布。

各组件的权威授权以其官方项目为准;下表为概述,便于采用单位做合规查核。

## 后端执行依赖(Python)

| 组件 | 授权 |
|---|---|
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| SQLAlchemy | MIT |
| Alembic | MIT |
| **psycopg (psycopg3)** | **LGPL-3.0-or-later** |
| Pydantic / pydantic-settings | MIT |
| redis-py | MIT |
| RQ (rq) | BSD-3-Clause |
| python-multipart | Apache-2.0 |
| bcrypt | Apache-2.0 |
| itsdangerous | BSD-3-Clause |
| openpyxl | MIT |
| OR-Tools | Apache-2.0 |
| WeasyPrint(worker 导出用) | BSD-3-Clause |

## worker 镜像的系统组件(Debian,以系统程序库或子进程使用)

| 组件 | 授权 | 使用方式 |
|---|---|---|
| **poppler-utils**(`pdftoppm`) | **GPL-2.0** | 以**子进程**调用,转 PDF→PNG |
| Pango / Cairo / gdk-pixbuf | LGPL | WeasyPrint 的系统依赖(动态链接) |
| fonts-noto-cjk(Noto Sans/Serif CJK) | SIL Open Font License 1.1 | 内嵌于导出的 PDF |
| postgresql-client(`pg_dump`/`pg_restore`) | PostgreSQL License(宽松) | 以子进程调用,备份/恢复 |

## 前端依赖

| 组件 | 授权 |
|---|---|
| Vue 3 / Vue Router / Pinia | MIT |
| Naive UI | MIT |
| Vite | MIT |

## 执行时基础镜像(由部署者自官方来源拉取,非本项目散布)

| 镜像 | 授权 |
|---|---|
| PostgreSQL(`postgres:16-alpine`) | PostgreSQL License |
| Redis(`redis:7-alpine`) | BSD-3-Clause / 视版本 |
| Caddy(`caddy:2-alpine`) | Apache-2.0 |

## 关于 copyleft 组件的说明

- **psycopg(LGPL-3.0)**:以独立函数库**动态依赖**方式使用(未修改、未静态链接进本项目)。LGPL 对此种使用不要求本项目采用相同授权,故 MIT 兼容。
- **poppler-utils / `pdftoppm`(GPL-2.0)**:仅以**子进程**调用的独立命令列程序(mere aggregation),GPL 的 copyleft 不延伸至调用它的本项目代码。
- **Pango / Cairo 等(LGPL)**:动态链接的系统程序库,与上述 LGPL 说明同理。

若你要**修改并再散布**这些 copyleft 组件本身(而非仅使用),请遵循其各自的授权条款。单纯部署与使用本系统不涉及此义务。
