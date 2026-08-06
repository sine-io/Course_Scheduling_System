#!/usr/bin/env bash
# 学校排课、调课与代课管理系统 — Linux / macOS / NAS 一键安装
#
# 把「建文件夹 → 下载配置文件 → 编辑 .env → 启动 → 找出访问地址」压成一次执行。
# 过程只问三件事:校名、管理员密码、对外端口号;SECRET_KEY 自动生成。
#
# 刻意设计成「下载后执行」而非 curl | sh:这是要进学校主机的东西,
# 用户应该能先打开看过内容再跑。
#
#   curl -fLO https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/main/install.sh
#   less install.sh          # 先看过
#   bash install.sh
#
# 用法:bash install.sh [选项]
#   --path <目录>        安装位置(默认 ~/scheduling)
#   --school-name <名称> 校名
#   --admin-password <密码>
#   --port <端口号>        对外端口号(默认 80,被占用时自动改建议值)
#   --project-name <名称> compose 项目名称(默认 scheduling)。同名 = 同一套部署,
#                        要在同一台主机再装一套(如测试环境)必须指定不同名称
#   --timezone <时区>    默认 Asia/Shanghai
#   --ref <分支或标签>   要拉哪一版配置文件(默认 main)
#   --image-tag <标签>   映像版本(默认 latest)
#   --skip-start         只生成配置文件,不启动
#   --reconfigure        已安装过时,重新设置 .env
#   --yes                不询问,全用默认值/参数值

set -euo pipefail

REPO_URL="https://github.com/sine-io/Course_Scheduling_System"
REF="main"
INSTALL_PATH="${HOME}/scheduling"
SCHOOL_NAME=""
ADMIN_PASSWORD=""
PORT=""
PROJECT_NAME=""
TIMEZONE="Asia/Shanghai"
IMAGE_TAG="latest"
SKIP_START=0
RECONFIGURE=0
ASSUME_YES=0

while [ $# -gt 0 ]; do
  case "$1" in
    --path)           INSTALL_PATH="$2"; shift 2 ;;
    --school-name)    SCHOOL_NAME="$2"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
    --port)           PORT="$2"; shift 2 ;;
    --project-name)   PROJECT_NAME="$2"; shift 2 ;;
    --timezone)       TIMEZONE="$2"; shift 2 ;;
    --ref)            REF="$2"; shift 2 ;;
    --image-tag)      IMAGE_TAG="$2"; shift 2 ;;
    --skip-start)     SKIP_START=1; shift ;;
    --reconfigure)    RECONFIGURE=1; shift ;;
    --yes|-y)         ASSUME_YES=1; shift ;;
    -h|--help)        sed -n '2,29p' "$0"; exit 0 ;;
    *) echo "未知的选项:$1(用 --help 看说明)" >&2; exit 1 ;;
  esac
done

RAW_BASE="https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/${REF}"

# ── 输出小工具 ────────────────────────────────────────────────
if [ -t 1 ]; then
  C_HEAD=$'\033[36m'; C_OK=$'\033[32m'; C_WARN=$'\033[33m'
  C_ERR=$'\033[31m';  C_DIM=$'\033[90m'; C_OFF=$'\033[0m'
else
  C_HEAD=""; C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""; C_OFF=""
fi
head_()  { printf '\n  %s%s%s\n' "$C_HEAD" "$1" "$C_OFF"; }
step_()  { printf '  → %s\n' "$1"; }
ok_()    { printf '  %s✓ %s%s\n' "$C_OK" "$1" "$C_OFF"; }
note_()  { printf '    %s%s%s\n' "$C_DIM" "$1" "$C_OFF"; }
attn_()  { printf '  %s! %s%s\n' "$C_WARN" "$1" "$C_OFF"; }
die_() {
  printf '\n  %s✗ %s%s\n' "$C_ERR" "$1" "$C_OFF"; shift
  for line in "$@"; do printf '    %s%s%s\n' "$C_WARN" "$line" "$C_OFF"; done
  printf '\n'; exit 1
}

# ── 1. Docker 检查 ───────────────────────────────────────────
head_ '[1/5] 检查 Docker'

if ! command -v docker >/dev/null 2>&1; then
  die_ '找不到 Docker。' \
    '本系统以 Docker 执行。在 Ubuntu / Debian 可用官方脚本安装:' \
    '' \
    '  curl -fsSL https://get.docker.com | sudo sh' \
    '  sudo usermod -aG docker $USER' \
    '' \
    '然后「登出再登录」让群组生效,然后重新执行本脚本。' \
    'NAS(Synology / QNAP)请先在软件包中心安装 Container Manager / Container Station。'
fi

if ! sudo docker info >/dev/null 2>&1; then
  # 权限不足与引擎没开是两件事,错误消息长得很像,但解法完全不同
  if sudo docker info 2>&1 | grep -qi 'permission denied'; then
    die_ '目前的用户没有权限操作 Docker。' \
      '把自己加进 docker 群组,然后「登出再登录」(只重开终端机不够):' \
      '' \
      '  sudo usermod -aG docker $USER' \
      '' \
      '或者这次先用 sudo 执行:sudo bash install.sh'
  fi
  die_ 'Docker 已安装,但引擎没有在执行。' \
    '请先启动 Docker:' \
    '' \
    '  sudo systemctl start docker' \
    '' \
    'macOS 请开启 Docker Desktop,等菜单列的鲸鱼图示不再转动。'
fi
ok_ "Docker 引擎执行中(版本 $(sudo docker version --format '{{.Server.Version}}' 2>/dev/null || echo '未知'))"

if ! sudo docker compose version >/dev/null 2>&1; then
  die_ '这个 Docker 没有 Compose 外挂。' \
    '请升级 Docker(近期版本内置 Compose v2),或安装 docker-compose-plugin。' \
    '注意:旧的 docker-compose(有连字符)不适用,本项目需要 sudo docker compose v2。'
fi
ok_ 'Docker Compose 可用'

# ── 2. 目录与配置文件 ──────────────────────────────────────────
head_ '[2/5] 准备安装目录'
mkdir -p "$INSTALL_PATH"
INSTALL_PATH="$(cd "$INSTALL_PATH" && pwd)"
ok_ "使用目录 $INSTALL_PATH"

# compose 的项目名称决定「哪些容器与 volume 属于同一套」。默认写死在
# docker-compose.yml 的 name: scheduling,可由 .env 的 COMPOSE_PROJECT_NAME 盖过。
resolve_project_() {
  if [ -n "$PROJECT_NAME" ]; then
    case "$PROJECT_NAME" in
      [a-z0-9]*) ;;
      *) die_ "项目名称「${PROJECT_NAME}」不合法。" \
           'Docker 要求:只能用小写英数字、底线与连字符,且开头须为英数字。' \
           '例如:scheduling-test' ;;
    esac
    if printf '%s' "$PROJECT_NAME" | grep -q '[^a-z0-9_-]'; then
      die_ "项目名称「${PROJECT_NAME}」不合法。" \
        'Docker 要求:只能用小写英数字、底线与连字符,且开头须为英数字。'
    fi
    printf '%s' "$PROJECT_NAME"; return
  fi
  if [ -f "${INSTALL_PATH}/.env" ]; then
    local found
    found="$(sed -n 's/^COMPOSE_PROJECT_NAME="\?\([^"[:space:]]\+\)"\?.*/\1/p' \
             "${INSTALL_PATH}/.env" | tail -1)"
    if [ -n "$found" ]; then printf '%s' "$found"; return; fi
  fi
  printf 'scheduling'   # 与 docker-compose.yml 的 name: 一致
}

# 同名项目若指向别的目录,sudo docker compose up 会直接接管那一套——包含它的数据库 volume。
# 这是本脚本唯一可能毁掉既有数据的路径,所以挡在启动之前。
assert_no_conflict_() {
  local project="$1" mine others answer
  mine="${INSTALL_PATH}/docker-compose.yml"
  others="$(sudo docker ps -a --filter "label=com.docker.compose.project=${project}" \
            --format '{{.Label "com.docker.compose.project.config_files"}}' 2>/dev/null \
            | grep -v '^$' | sort -u | grep -vxF "$mine" || true)"
  [ -n "$others" ] || return 0

  printf '\n'
  attn_ "这台主机上已经有一套名为「${project}」的部署,但它在别的文件夹:"
  printf '%s\n' "$others" | while IFS= read -r o; do note_ "  $o"; done
  printf '\n'
  attn_ '继续下去会「接管」那一套,而不是另外装一套新的——'
  attn_ '它的容器会被依这里的设置重建,数据库 volume 也是同一份。'
  printf '\n'
  note_ '若你要的是「再装一套独立的测试环境」,请改用不同的项目名称重跑,例如:'
  note_ '  bash install.sh --project-name scheduling-test --path ~/scheduling-test'
  printf '\n'

  if [ "$ASSUME_YES" = "1" ]; then
    die_ '为避免误覆盖既有部署,--yes 模式下不接管别的目录。' \
      '请加上 --project-name 指定新名称,或移除 --yes 以交互方式确认。'
  fi
  read -r -p '  确定要接管既有的那一套吗?(输入 yes 继续,其他任意键取消) ' answer </dev/tty || answer=""
  if [ "$answer" != "yes" ]; then printf '\n  已取消。\n\n'; exit 0; fi
}

fetch_() {
  # NAS 上常常只有 wget 没有 curl,两个都试
  local url="$1" dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$dest" && return 0
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$dest" "$url" && return 0
  else
    die_ '系统上既没有 curl 也没有 wget,无法下载配置文件。' \
      '请先安装其一(例:sudo apt install curl)。'
  fi
  die_ "下载失败:$url" \
    '请确认这台主机能连上互联网(GitHub)。若学校网络有防火墙或 Proxy,' \
    '可手动下载下列两个文件放进安装目录,再加 --skip-start 重跑:' \
    "  ${RAW_BASE}/docker-compose.yml" \
    "  ${RAW_BASE}/.env.example"
}

PROJECT="$(resolve_project_)"
assert_no_conflict_ "$PROJECT"

head_ '[3/5] 获取配置文件'
fetch_ "${RAW_BASE}/docker-compose.yml" "${INSTALL_PATH}/docker-compose.yml"
fetch_ "${RAW_BASE}/.env.example"       "${INSTALL_PATH}/.env.example"
ok_ '已下载 docker-compose.yml 与 .env.example'

# ── 3. 生成 .env ─────────────────────────────────────────────
gen_secret_() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -r /dev/urandom ] && command -v od >/dev/null 2>&1; then
    od -An -tx1 -N32 /dev/urandom | tr -d ' \n'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import secrets; print(secrets.token_hex(32))'
  else
    die_ '找不到可用的乱数来源,无法生成 SECRET_KEY。' \
      '请安装 openssl 后重试。'
  fi
}

port_free_() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ! ss -ltn "sport = :$p" 2>/dev/null | grep -q LISTEN
  elif command -v netstat >/dev/null 2>&1; then
    ! netstat -ltn 2>/dev/null | grep -qE "[:.]$p[[:space:]]"
  else
    return 0   # 查不到就别挡用户
  fi
}

ask_() {
  # $1=提示 $2=默认值
  local answer
  if [ "$ASSUME_YES" = "1" ]; then printf '%s' "$2"; return; fi
  read -r -p "  $1 [$2] " answer </dev/tty || answer=""
  if [ -z "$answer" ]; then printf '%s' "$2"; else printf '%s' "$answer"; fi
}

ask_password_() {
  local p1 p2
  while true; do
    read -r -s -p '  管理员密码(输入时不会显示): ' p1 </dev/tty; printf '\n'
    if [ "${#p1}" -lt 8 ]; then attn_ '至少 8 个字符,请重新输入。'; continue; fi
    case "$p1" in *'"'*|*'\'*) attn_ '请避免使用 " 与 \ 这两个字符。'; continue ;; esac
    read -r -s -p '  再输入一次确认: ' p2 </dev/tty; printf '\n'
    if [ "$p1" != "$p2" ]; then attn_ '两次输入不一致,请重来。'; continue; fi
    printf '%s' "$p1"; return
  done
}

write_env_() {
  # 以 .env.example 为底逐行取代,而不是自己拼一份:
  # 日后 .env.example 新增设置项时,这里会自动跟上,不会漏。
  local example="${INSTALL_PATH}/.env.example" dest="${INSTALL_PATH}/.env"
  ENV_ADMIN_USERNAME="admin" \
  ENV_ADMIN_PASSWORD="$1" \
  ENV_SCHOOL_NAME="$2" \
  ENV_TZ="$3" \
  ENV_SECRET_KEY="$4" \
  ENV_HTTP_PORT="$5" \
  ENV_IMAGE_TAG="$6" \
  ENV_HTTPS_PORT="$7" \
  ENV_COMPOSE_PROJECT_NAME="$8" \
  awk '
    function emit(k, v) {
      # sudo docker compose 会对 .env 的值做变量展开,值里的 $ 必须写成 $$。
      # 不 escape 的话,密码 my$ecret123 会被解读成 my + ${ecret123} 而变成 my,
      # 而且全程没有任何错误消息,用户只会发现自己登不进去。
      gsub(/\$/, "$$", v)
      # 含中文或空白的值加引号;纯数字/十六进位不加,避免被当字串
      if (v ~ /^[A-Za-z0-9_.:\/-]+$/) print k "=" v; else print k "=\"" v "\""
    }
    BEGIN {
      n = split("ADMIN_USERNAME ADMIN_PASSWORD SCHOOL_NAME TZ SECRET_KEY " \
                "HTTP_PORT HTTPS_PORT IMAGE_TAG COMPOSE_PROJECT_NAME", wanted, " ")
    }
    /^[A-Z_][A-Z0-9_]*=/ {
      key = substr($0, 1, index($0, "=") - 1)
      val = ENVIRON["ENV_" key]
      if (val != "") { emit(key, val); handled[key] = 1; next }
    }
    { print }
    END {
      # .env.example 里是注解掉的项目(如 HTTPS_PORT)不会被上面比对到,补在档尾
      first = 1
      for (i = 1; i <= n; i++) {
        k = wanted[i]
        v = ENVIRON["ENV_" k]
        if (v != "" && !(k in handled)) {
          if (first) { print ""; print "# ── 由安装程序加入 ──────────────────"; first = 0 }
          emit(k, v)
        }
      }
    }
  ' "$example" > "$dest"
  chmod 600 "$dest"   # 里面有密码,不让同机其他用户读
}

NEED_CONFIG=1
if [ -f "${INSTALL_PATH}/.env" ] && [ "$RECONFIGURE" = "0" ]; then
  attn_ '检测到既有的 .env,保留原设置(校名、密码、密钥都不动)。'
  note_ '要重新设置请加 --reconfigure 重跑。'
  NEED_CONFIG=0
fi

if [ "$NEED_CONFIG" = "1" ]; then
  printf '\n  %s请回答三个问题(直接按 Enter 即采用默认值):%s\n\n' "$C_HEAD" "$C_OFF"

  [ -n "$SCHOOL_NAME" ] || SCHOOL_NAME="$(ask_ '学校名称(显示在界面与课表上)' '示范学校')"

  if [ -z "$ADMIN_PASSWORD" ]; then
    if [ "$ASSUME_YES" = "1" ]; then die_ '--yes 需要同时提供 --admin-password。'; fi
    note_ '管理员账号固定为 admin,首次登录后系统会要求你再改一次密码。'
    ADMIN_PASSWORD="$(ask_password_)"
  else
    # 走参数的路径同样要挡:交互输入那边挡了,这边不阻止就成了漏洞
    [ "${#ADMIN_PASSWORD}" -ge 8 ] || die_ '--admin-password 至少需 8 个字符。'
    case "$ADMIN_PASSWORD" in *'"'*|*'\'*) die_ '--admin-password 不可含 " 或 \ 字符。' ;; esac
  fi

  if [ -z "$PORT" ]; then
    CANDIDATE=80
    if ! port_free_ 80; then
      attn_ '端口号 80 已被其他程序占用(常见于 Apache、Nginx 或另一套 Web 服务)。'
      CANDIDATE=8080
      while ! port_free_ "$CANDIDATE" && [ "$CANDIDATE" -lt 8100 ]; do
        CANDIDATE=$((CANDIDATE + 1))
      done
      note_ "改用 ${CANDIDATE}。往后访问地址要多带端口号,例如 http://主机IP:${CANDIDATE}"
    fi
    while true; do
      PORT="$(ask_ '对外连接端口' "$CANDIDATE")"
      case "$PORT" in
        ''|*[!0-9]*) attn_ '请输入数字。' ;;
        *) if [ "$PORT" -ge 1 ] && [ "$PORT" -le 65535 ]; then break; fi
           attn_ '请输入 1–65535 之间的数字。' ;;
      esac
    done
  fi

  # compose 是「无条件」发布 443 的,即使根本没启用 HTTPS。443 被别的服务占著时
  # web 容器会起不来,而 Docker 只说「Bind for 0.0.0.0:443 failed」,
  # 用户完全看不出跟自己设的 80 有什么关系。先帮他闪开。
  HTTPS_PORT=443
  if ! port_free_ 443; then
    HTTPS_PORT=8443
    while ! port_free_ "$HTTPS_PORT" && [ "$HTTPS_PORT" -lt 8500 ]; do
      HTTPS_PORT=$((HTTPS_PORT + 1))
    done
    attn_ "端口号 443 已被占用,HTTPS 端口改用 ${HTTPS_PORT}(目前走 HTTP,不影响使用)。"
  fi

  # 只在非默认时写入:留白的话就沿用 docker-compose.yml 里的 name: scheduling
  WRITE_PROJECT=""
  [ "$PROJECT" = "scheduling" ] || WRITE_PROJECT="$PROJECT"

  write_env_ "$ADMIN_PASSWORD" "$SCHOOL_NAME" "$TIMEZONE" "$(gen_secret_)" \
             "$PORT" "$IMAGE_TAG" "$HTTPS_PORT" "$WRITE_PROJECT"
  ok_ "已写入 ${INSTALL_PATH}/.env(含自动生成的 SECRET_KEY,权限 600)"
  [ -z "$WRITE_PROJECT" ] || note_ "此部署的项目名称为 ${PROJECT}(记在 .env,后续指令会自动沿用)"
  note_ '这个文件含有密码,请勿上传到云端硬盘或 GitHub。'
fi

# 读回实际生效的端口号(保留既有 .env 时,以文件里的为准)
ACTIVE_PORT="$(sed -n 's/^HTTP_PORT="\?\([0-9]\+\)"\?.*/\1/p' "${INSTALL_PATH}/.env" | tail -1)"
[ -n "$ACTIVE_PORT" ] || ACTIVE_PORT=80

if [ "$SKIP_START" = "1" ]; then
  head_ '已生成配置文件,依 --skip-start 未启动'
  note_ "检查无误后,在 ${INSTALL_PATH} 执行:sudo docker compose up -d"
  printf '\n'; exit 0
fi

# ── 4. 启动 ──────────────────────────────────────────────────
head_ '[4/5] 下载映像并启动(首次约需数分钟)'
cd "$INSTALL_PATH"

step_ '下载官方映像…'
if ! sudo docker compose pull; then
  die_ '映像下载失败。' \
    '常见原因:网络不通、或学校防火墙阻止 ghcr.io。' \
    '可改用「从源代码构建」的方式,见安装指南。'
fi

step_ '启动六个容器…'
if ! sudo docker compose up -d --wait --wait-timeout 300; then
  sudo docker compose ps || true
  die_ '容器启动未成功。' \
    "请在 ${INSTALL_PATH} 执行下列指令查看原因:" \
    '  sudo docker compose logs --tail 50' \
    '' \
    '若错误消息提到 "port is already allocated",是端口号被占用:' \
    '改 .env 的 HTTP_PORT(网页端口)或 HTTPS_PORT(即使没用 HTTPS 也会被占用),' \
    '然后重跑 sudo docker compose up -d'
fi

step_ '确认系统响应…'
HEALTHY=0
TRIES=0
while [ "$TRIES" -lt 30 ]; do
  TRIES=$((TRIES + 1))
  if command -v curl >/dev/null 2>&1; then
    curl -fsS "http://localhost:${ACTIVE_PORT}/api/health" >/dev/null 2>&1 && { HEALTHY=1; break; }
  else
    wget -qO- "http://localhost:${ACTIVE_PORT}/api/health" >/dev/null 2>&1 && { HEALTHY=1; break; }
  fi
  sleep 2
done
if [ "$HEALTHY" = "1" ]; then ok_ '系统已可用'
else attn_ '容器起来了,但健康检查没过。稍等一分钟再开网页看看。'; fi

# ── 5. 完成 ──────────────────────────────────────────────────
lan_address_() {
  if command -v hostname >/dev/null 2>&1 && hostname -I >/dev/null 2>&1; then
    hostname -I | tr ' ' '\n' | grep -v '^$' | grep -v '^127\.' | grep -v '^172\.1[7-9]\.' | head -1
  elif command -v ipconfig >/dev/null 2>&1; then
    ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true
  elif command -v ip >/dev/null 2>&1; then
    ip -4 -o addr show scope global 2>/dev/null | awk '{split($4,a,"/"); print a[1]}' | head -1
  fi
}

SUFFIX=""
[ "$ACTIVE_PORT" = "80" ] || SUFFIX=":${ACTIVE_PORT}"
LAN="$(lan_address_ || true)"

head_ '[5/5] 安装完成'
printf '\n  在这台主机上开:\n'
printf '    %shttp://localhost%s%s\n' "$C_OK" "$SUFFIX" "$C_OFF"
if [ -n "$LAN" ]; then
  printf '  校内其他电脑开:\n'
  printf '    %shttp://%s%s%s\n' "$C_OK" "$LAN" "$SUFFIX" "$C_OFF"
  note_ '(若连不到,多半是主机防火墙阻止,需放行该端口号)'
fi
printf '\n  账号 admin,密码是你刚才设置的那组;登录后会要求改一次密码,\n'
printf '  然后进入「设置精灵」,照画面五个步骤建立学期、教师、班级、科目。\n\n'
note_ "安装目录:${INSTALL_PATH}"
note_ '停止:sudo docker compose down    重新启动:sudo docker compose up -d(需先 cd 到上面的目录)'
note_ "操作手册与部署文件:${REPO_URL}"
printf '\n'
