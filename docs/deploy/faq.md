# 常见问题 FAQ

## 安装与启动

**Q：执行 `sudo docker compose up -d` 后，网页显示“502”或“无法连接”。**
容器可能还在启动(尤其首次要跑数据库迁移)。等 20–30 秒再试,并看状态:

```bash
sudo docker compose ps          # 查看服务是否均为 healthy
sudo docker compose logs api    # 查看 API 是否卡在迁移或发生错误
```

**Q：执行 `sudo docker compose ps` 时，有容器一直处于 restarting 状态。**
看该容器 log 找原因:

```bash
sudo docker compose logs --tail=50 <服务名>   # 例如 api / worker / postgres
```

常见:`.env` 的 `DATABASE_URL` 与 `POSTGRES_*` 账号和密码不一致;`SECRET_KEY` 未设。

**Q:80 端口被占用,启动失败(port is already allocated)。**
修改 `.env` 中的 `HTTP_PORT`（例如 `8080`），再执行 `sudo docker compose up -d`，然后访问 `http://<主机IP>:8080`。

**Q:校内其他电脑连不到。**
确认用的是主机的**局域网 IP**(非 `localhost`),且主机防火墙放行该端口。手机/平板需与主机同一网段(同一 Wi-Fi)。

---

## 账号与登录

**Q:忘记管理员密码怎么办?**
若你还记得 `.env` 的初始 `ADMIN_PASSWORD`,那是**首次登录**用的;登录后改过的密码存在数据库。若连改过的都忘了,目前需由具数据库访问权者重设。最务实的做法是**恢复一份记得密码的旧备份**(见[备份指南](backup.md)),或联系维护者。请妥善保管管理员密码。

**Q:恢复备份后大家被登出了。**
这是预期行为。恢复会替换整个数据库(含账号),为安全起见系统会强制所有人以恢复时点的账号和密码重新登录。

**Q:老师收不到调课与代课 Email。**
Email 为**选配**;未在「系统管理」设置 SMTP 时,只有站内通知(铃铛),系统一切正常。要寄 Email 需填学校的 SMTP 主机信息,并可按「寄测试信」当场验证。

---

## 数据与备份

**Q:我的数据存在哪?会不会不见?**
数据保存在 Docker 卷 `pgdata` 中。只要不删除该卷，执行 `sudo docker compose down`、重启或升级都不会影响数据。主机硬盘损坏时卷也会丢失，因此必须做好[异地备份](backup.md)。

**Q：执行 `sudo docker compose down` 会删除数据吗？**
不会。`down` 只停止并移除容器，数据卷会保留。**只有 `sudo docker compose down -v` 中的 `-v` 会删除数据卷及其中的数据**，请勿误用。

**Q:怎么把系统搬到新主机?**
新主机装好空系统 → 旧主机下载一份备份 `.dump` → 新主机「系统管理 → 上传恢复」。详见[备份指南](backup.md)。

---

## 性能与规模

**Q:自动排课很慢或跑不出来。**
排课是计算密集工作,受班级数、约束复杂度影响。建议主机 ≥ 4 核 8GB。无解时系统会给「冲突定位」报告,依提示放宽条件或补资源。可设置求解超时(默认 10 分钟),超时取当前最佳解。

**Q:页面偶尔转圈久。**
自动排课或大量导出时 worker 会比较繁忙，但它与 API 服务相互独立，一般操作不受影响。自 v1.1 起，排课（`worker`）与导出/备份（`worker-ops`）由不同容器负责，排课进行中提交导出任务仍会立即响应。若持续缓慢，请执行 `sudo docker stats` 检查主机资源使用情况。

**Q:导出/备份时出现「运维背景服务(worker-ops)没有在执行」。**

你的 `docker-compose.yml` 少了 `worker-ops` 这个容器(多半是用了旧版的 Compose 文件)。它负责导出、备份、恢复、发送邮件与每日自动备份——没有它,这些功能全都没人处理,而且**每日自动备份是无声停摆的**。

获取最新的 Compose 文件再重启即可,数据不受影响:

```bash
curl -fLO https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/main/docker-compose.yml
sudo docker compose up -d
sudo docker compose ps          # 应看到六个容器，包括 worker 和 worker-ops
```

**Q:导出课表 / 备份失败,说「背景忙碌或超时」。**

`worker-ops` 有在跑但没做完。查它的 log:

```bash
sudo docker compose ps worker-ops
sudo docker compose logs --tail=50 worker-ops
```

PDF/PNG 导出在配置较低的机器上偶尔会超过 90 秒；如果 `sudo docker stats` 显示资源紧张，请等待自动排课完成后重试。

---

## 升级与版本

**Q:怎么知道有没有新版、这版改了什么?**
看项目 [CHANGELOG.md](../../CHANGELOG.md) 与 GitHub Releases。升级步骤见[升级指南](upgrade.md)。

**Q:升级会不会弄坏数据?**
数据表结构变更由 `api` 启动时自动、向前兼容地迁移,数据保留。仍建议升级前先「立即备份」。破坏性变更(若有)会在 CHANGELOG 该版本以 ⚠️ 标注。

---

## 其他

**Q:可以多所学校共用一套吗?**
本系统设计为**单校自建**,一所学校一套部署,数据彼此隔离、最单纯也最安全。多校请各自部署。

**Q:如何完全移除?**

```bash
sudo docker compose down -v     # ⚠️ 会连同数据卷一起删除且无法恢复，请先备份！
```

**Q:找不到答案 / 想反馈问题?**
在项目 GitHub 创建 Issue（见 [CONTRIBUTING.md](../../CONTRIBUTING.md)）。报告时附上 `sudo docker compose logs` 的相关片段，有助于更快定位问题。
