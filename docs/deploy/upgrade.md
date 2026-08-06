# 升级指南

> **首次安装的人不需要这一页**,直接看[安装指南](install.md)。这里讲的是「已经在用,想换到新版」。

系统采「向前兼容迁移」:升级时**数据保留**,数据表结构的变更由 `api` 容器启动时自动执行(`alembic upgrade head`),你不需要手动改数据库。

> **开始前先备份。** 升级本身不会删数据,但任何重大操作前留一份备份是好习惯。到「系统管理 → 数据备份与恢复 → 立即备份」,或见[备份指南](backup.md)。

## 一条规则:`docker-compose.yml` 要跟着版本走

系统的容器组成会随版本演进(例如 v1.1 就多了一个 `worker-ops` 容器)。**升级时请连 `docker-compose.yml` 一起更新到新版**——方式 A 重新下载该档,方式 B 的 `git pull` 会自动带到。

沿用旧 Compose 文件而缺少新容器时，系统会立即返回包含处理方法的错误（例如“运维后台服务 worker-ops 未运行，请更新 docker-compose.yml”）。补齐新文件后执行 `sudo docker compose up -d` 即可恢复，数据不受影响。

---

## 方式 A:拉取镜像部署(最常见)

在放 `docker-compose.yml` 的文件夹内:

```bash
# 1)(建议)先在系统内按「立即备份」

# 2) 更新 docker-compose.yml 到新版(容器组成可能有变动)
#    https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/main/docker-compose.yml

# 3) 选择版本:编辑 .env
#    固定版本(可控):IMAGE_TAG=v1.2.0
#    永远最新:        IMAGE_TAG=latest

# 4) 拉新镜像并重启
sudo docker compose pull
sudo docker compose up -d
```

`sudo docker compose up -d` 只会重建镜像发生变化的容器；API 启动时会自动执行迁移。完成后：

```bash
sudo docker compose ps                 # 确认均为 healthy
curl http://localhost/api/health  # {"status":"ok"}
```

登录确认数据都在、版本正确(页尾/关于页显示版本号)。

---

## 方式 B:从源代码构建部署

```bash
git pull                 # 获取新版源代码
sudo docker compose up -d --build   # 重新构建并重启
```

---

## 关于版本固定

- **正式环境建议 `IMAGE_TAG=v1.2.0` 这样钉住特定版本**,你才能决定何时升级、升到哪一版,而不是每次 `pull` 都可能变动。
- 升级时，将 `IMAGE_TAG` 改为新版本号，再执行 `sudo docker compose pull && sudo docker compose up -d`。
- 各版本的变更内容见项目根目录的 [CHANGELOG.md](../../CHANGELOG.md);破坏性变更(若有)会在该版本明确标注 ⚠️ 与对应处理方式。

---

## 回滚(升级后想退回旧版)

因为数据与镜像分离,回滚镜像很单纯:

```bash
# .env 改回旧版本号,例如 IMAGE_TAG=v1.1.0
sudo docker compose pull
sudo docker compose up -d
```

> ⚠️ **注意数据库迁移方向**:若新版本引入了数据表结构变更,退回旧镜像后旧版程序可能无法识别新结构。**最稳妥的回滚方式是:退回旧镜像 + 恢复「升级前那份备份」**(见[备份指南](backup.md)的恢复流程)。若该次升级的 CHANGELOG 未标注 schema 变更,则只需更换镜像。

---

## 升级检查列表

- [ ] 升级前已「立即备份」
- [ ] 已读该版本 CHANGELOG,确认有无 ⚠️ 破坏性变更
- [ ] **`docker-compose.yml` 已更新到新版**(容器组成可能有变动)
- [ ] `sudo docker compose pull` 成功拉取新镜像
- [ ] `sudo docker compose up -d` 后六个容器均为 healthy
- [ ] `/api/health` 回 ok,登录数据完整
- [ ] (如有 schema 变更)确认关键页面正常
