# 安装指南

从零把系统架起来。整个过程约 15 分钟(含下载镜像)。

---

## 步骤 0:先装好 Docker

系统以 Docker Compose 运行,主机只需要装 **Docker**(含 Docker Compose,现代版本已内置)。

### Windows

1. 下载并安装 [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)。
2. 安装时若提示启用 WSL 2,照着开启即可。
3. 安装后开启 Docker Desktop,等左下角变绿灯(Engine running)。
4. 打开 Docker Desktop，确认界面显示 Docker Engine 正在运行。

### Linux(Ubuntu / Debian,校内服务器常见)

```bash
curl -fsSL https://get.docker.com | sudo sh
```

执行 `sudo docker compose version` 能显示版本号即表示安装成功。

### NAS(Synology / QNAP)

- **群晖 NAS**：在 DSM 中安装 **Container Manager**（旧机型显示为 Docker）。DSM 7.2 及以上版本可在 Container Manager 的“项目”页导入 `docker-compose.yml`。
- **QNAP**:「App Center」安装 **Container Station**,其中的「应用程序(Applications)」支持 docker-compose.yml。
- NAS 内存建议 ≥ 4GB;自动排课较吃资源,尖峰时建议 8GB。

> NAS 图形界面的操作细节各机型略有差异,但核心都是「粘贴 compose 设置 → 提供 .env 环境变量 → 创建项目」。以下命令列步骤同样适用于在 NAS 上开 SSH 操作。

---

## 步骤 1:获取配置文件

### 一键安装脚本(推荐)

脚本会检查 Docker、交互生成 `.env`、下载匹配版本的 Compose 文件并启动服务。正式环境建议填写明确的版本标签。

Linux、macOS 或支持 SSH 的 NAS:

```bash
curl -fsSL https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/main/install.sh -o install.sh
chmod +x install.sh
./install.sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/main/install.ps1 -OutFile install.ps1
.\install.ps1
```

需要自定义安装目录、端口、Compose 项目名称、镜像版本，或只生成配置文件时，执行 `./install.sh --help` 或 `Get-Help .\install.ps1 -Detailed` 查看参数。脚本检测到同名项目位于其他目录时会要求确认，避免误接管已有数据库卷。

以下步骤适合希望手工管理配置文件的用户。

### 方式 A:拉取官方预建镜像(推荐)

只需要两个文件:`docker-compose.yml` 与 `.env`。创建一个空文件夹(例如 `scheduling`),放入本项目的 `docker-compose.yml`,并在同层创建 `.env`(见步骤 2)。

```bash
mkdir scheduling && cd scheduling
# 下载 docker-compose.yml 与 .env.example(从项目 Releases 页或源代码获取)
curl -fLO https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/main/docker-compose.yml
curl -fL  https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/main/.env.example -o .env
```

### 方式 B:从源代码构建

```bash
git clone https://github.com/sine-io/Course_Scheduling_System.git
cd Course_Scheduling_System
cp .env.example .env
```

---

## 步骤 2:修改 `.env`(至少改两项)

用文字编辑器打开 `.env`,**最少**改这几项:

```ini
ADMIN_PASSWORD=改成你的管理员密码      # 首次登录后系统会再要求你改一次
SCHOOL_NAME=海州市启明实验初级中学     # 首次启动值，之后可在系统管理中修改
SECRET_KEY=改成一长串随机字符          # 见下方生成方式,务必更换
```

**生成随机 `SECRET_KEY`**(用于签署会话信息,关系到登录安全,一定要换掉默认值):

```bash
openssl rand -hex 32        # Linux/Mac/Git Bash
```

其余设置(数据库账号和密码、Redis)保持默认即可。系统时区固定为 `Asia/Shanghai`，无需配置。详细说明见 `.env.example` 内的注释。

> **`.env` 含机密,切勿上传到 GitHub、云端硬盘或任何公开处。** 本项目的 `.gitignore` 已排除它。

---

## 步骤 3:启动

### 方式 A(拉取镜像)

```bash
sudo docker compose pull      # 下载官方镜像（首次耗时较长）
sudo docker compose up -d     # 后台启动六个容器
```

### 方式 B(从源代码构建)

```bash
sudo docker compose up -d     # 首次会自动构建镜像，通常需要几分钟
```

启动后首次会**自动执行数据库迁移**(创建所有数据表),你不需要手动做任何 SQL。

---

## 验证安装成功

```bash
sudo docker compose ps        # 六个容器均应为 running / healthy
curl http://localhost/api/health
# 预期响应:{"status":"ok"}
```

用浏览器开:

- 本机:<http://localhost>
- 校内其他电脑:`http://<主机的局域网IP>`(例如 `http://192.168.1.50`,IP 用 `ipconfig` / `ip a` 查)

以 `.env` 设置的 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 登录,系统会要求你**首次改密码**,接着进入**设置向导**,按页面上的五个步骤创建学期、教师、班级、科目即可开始使用。

---

## 硬件最低需求

| 项目 | 最低 | 建议(含自动排课) |
|---|---|---|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 磁盘 | 10 GB | 20 GB(含备份保留 30 份) |
| 架构 | x86-64 或 ARM64(NAS/树莓派可) | — |

官方镜像同时提供 `linux/amd64` 与 `linux/arm64`,Docker 会自动挑选符合你主机的版本。

---

## 端口号被占用怎么办?

默认对外走 80 端口。若该端口已被其他服务使用,改 `.env`:

```ini
HTTP_PORT=8080
```

重新执行 `sudo docker compose up -d`，然后访问 `http://<主机IP>:8080`。

---

下一步:设置[每日自动备份与异地备份](backup.md);若要让校外也能连,见[域名与 HTTPS](https.md)。遇到问题见 [FAQ](faq.md)。
