# ADR-0015：API 与后台任务共用单一 backend 镜像

状态：已接受（2026-09-15）。

正式与开发 Compose 将 `api`、`worker` 和 `worker-ops` 的运行时统一为同一个 `ghcr.io/sine-io/course_scheduling_system-backend` 镜像（Dockerfile 的 `worker` target）；三个服务仍以独立容器和不同命令运行。这样只需构建、发布和缓存一个后端镜像，同时保留 default/ops 队列的故障、资源与重启隔离。`base` target 保留为内部基础层，API 会随统一镜像携带 PDF、备份和求解器依赖，这是可接受的体积换空间易管理性的取舍；若以后优先追求下载体积，再另行评估拆分依赖。
