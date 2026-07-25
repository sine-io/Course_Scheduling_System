# 域名与 HTTPS(选配)

**校内网络使用不需要这篇** —— 用 `http://<主机IP>` 即可,免设置。

本篇适用于:要让**校外**(在家、手机移动网络)也能连,并使用域名 + HTTPS 加密。系统的 web 容器用 Caddy,设置域名后会**自动申请并续期 Let's Encrypt 证书**,你不必手动处理证书。

---

## 你需要先具备

1. **一个域名**（例如 `school.example.edu.cn`，也可以使用自有域名）。
2. 一台**具公开 IP 的主机**(校内对外服务器,或云端 VPS)。
3. 能编辑该域名的 **DNS**,把域名指向主机 IP。
4. 主机的 **80 与 443 端口可从外网连入**(防火墙/网络安全设备放行;Let's Encrypt 签发需要 80 端口)。

---

## 设置步骤

### 1. DNS 指向主机

在域名管理处新增一条 **A 记录**:

```
school.example.edu.cn   →   你的主机公网 IP
```

等待 DNS 生效（通常需要几分钟到几十分钟）。可用 `nslookup school.example.edu.cn` 确认解析到正确 IP。

### 2. 在 `.env` 设置域名

```ini
SITE_ADDRESS=school.example.edu.cn
HTTPS_PORT=443
```

- `SITE_ADDRESS` 一填成域名,Caddy 就会自动走 HTTPS 并把 HTTP 转址到 HTTPS。
- 不填(或留 `:80`)则保持内网 HTTP 模式。

### 3. 重启

```bash
sudo docker compose up -d
sudo docker compose logs -f web     # 查看证书申请过程
```

首次启动时，Caddy 会向 Let's Encrypt 申请证书；日志出现 `certificate obtained successfully` 即表示成功。之后可通过 `https://school.example.edu.cn` 访问，浏览器应显示安全锁标志。

证书存放于 `caddydata` volume,重启不会重新申请;续期由 Caddy 自动处理。

---

## 在云端 VPS 上部署(校内无法对外时)

若学校网络无法对外开端口,可租一台小型 VPS(1–2 vCPU / 2–4GB RAM 即可跑基本功能,自动排课建议 4 核 8GB):

1. 依[安装指南](install.md)在 VPS 上装好 Docker 并起好系统。
2. 依本篇设置域名与 `SITE_ADDRESS`。
3. VPS 防火墙/安全群组放行 **80、443**;**不要**对外开放 5432(PostgreSQL)、6379(Redis)、8000(api)——这些只在容器内部网络互通,compose 默认也不对外映射它们。

> **数据落在 VPS 上**,务必依[备份指南](backup.md)设好异地备份(定期下载 `.dump` 到校内或云端硬盘)。VPS 若停租或损毁,只有异地备份能救回数据。

---

## 常见状况

**证书申请失败(log 出现 challenge failed / timeout)**
- 多半是 80/443 没对外通,或 DNS 还没指到这台主机。先确认外网能连到主机的 80 端口。
- 域名必须是**真实可解析**的公开域名;`localhost` 或纯 IP 无法申请公开证书。

**只想要 HTTPS 但用自签/内部证书(纯内网)**
- Caddy 对非公开域名可用其内部 CA。高级需求请参考 [Caddy 官方文件](https://caddyserver.com/docs/),或改用纯 HTTP 内网部署。

**改了域名要换成另一个**
- 修改 `.env` 中的 `SITE_ADDRESS` 后，执行 `sudo docker compose up -d`。旧证书保留在 `caddydata` 中，不影响使用。

**80 端口被学校现有网站占用**
- HTTPS 自动签发需要 80 端口做验证,较难共用。建议此场景改用独立 VPS,或与网管协调子域名与端口。
