#Requires -Version 5.1
<#
.SYNOPSIS
    学校排课、调课与代课管理系统 — Windows 一键安装

.DESCRIPTION
    把「建文件夹 → 下载配置文件 → 编辑 .env → 启动 → 找出访问地址」压成一次执行。
    过程只问三件事:校名、管理员密码、对外端口号;SECRET_KEY 自动生成。

    刻意设计成「下载后执行」而非 irm | iex:这是要进学校主机的东西,
    用户应该能先打开看过内容再跑。

.EXAMPLE
    .\install.ps1
    交互安装到 %USERPROFILE%\scheduling。

.EXAMPLE
    .\install.ps1 -InstallPath D:\scheduling -Port 8080
    指定安装位置与端口号,其余仍会询问。

.EXAMPLE
    .\install.ps1 -SchoolName "海州市启明实验初级中学" -AdminPassword "..." -Port 80 -Yes
    完全不交互(供自动化或重建环境使用)。

.LINK
    https://github.com/sine-io/Course_Scheduling_System
#>
[CmdletBinding()]
param(
    # 安装目录。里面只会有 docker-compose.yml 与 .env,数据都在 Docker volume
    [string]$InstallPath = (Join-Path $HOME 'scheduling'),
    [string]$SchoolName,
    [string]$AdminPassword,
    [ValidateRange(1, 65535)]
    [int]$Port,
    [string]$TimeZone = 'Asia/Shanghai',
    # Docker compose 项目名称。同名就是同一套部署——想在同一台主机上再装一套
    # (例如与正式环境并存的测试环境)必须指定不同的名称,否则会接管既有那一套。
    [string]$ProjectName,
    # 要拉哪一版配置文件与镜像。默认 main(最新);正式部署可固定为 v1.2.0
    [string]$Ref = 'main',
    [string]$ImageTag = 'latest',
    # 只生成配置文件,不启动(想先自己看过 .env 再手动 docker compose up -d 时用)
    [switch]$SkipStart,
    # 已安装过时,重新设置 .env(默认会保留既有设置,不动你的密码)
    [switch]$Reconfigure,
    # 全部用默认值/参数值,不询问
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# 旧版 Windows 默认不启用 TLS 1.2,不设会连不上 GitHub
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$RepoUrl = 'https://github.com/sine-io/Course_Scheduling_System'
$RawBase = "https://raw.githubusercontent.com/sine-io/Course_Scheduling_System/$Ref"

# PowerShell 5.1 的地雷:对原生程序做 2>&1 时,stderr 的每一行都会被包成 ErrorRecord,
# 在 $ErrorActionPreference='Stop' 之下会直接抛例外——即使该程序返回 0。
# docker 很爱往 stderr 写正常消息,所以凡是需要「收下输出并看结果」的呼叫都走这里。
function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Exe @Arguments 2>&1 | Out-String
        return [pscustomobject]@{ Ok = ($LASTEXITCODE -eq 0); Output = $out.Trim() }
    }
    finally { $ErrorActionPreference = $prev }
}

# ── 输出小工具 ────────────────────────────────────────────────
function Write-Head($t) { Write-Host ''; Write-Host "  $t" -ForegroundColor Cyan }
function Write-Step($t) { Write-Host "  → $t" -ForegroundColor White }
function Write-Ok($t)   { Write-Host "  ✓ $t" -ForegroundColor Green }
function Write-Note($t) { Write-Host "    $t" -ForegroundColor DarkGray }
function Write-Attn($t) { Write-Host "  ! $t" -ForegroundColor Yellow }

function Stop-WithHelp {
    param([string]$Message, [string[]]$Hints)
    Write-Host ''
    Write-Host "  ✗ $Message" -ForegroundColor Red
    foreach ($h in $Hints) { Write-Host "    $h" -ForegroundColor Yellow }
    Write-Host ''
    exit 1
}

function Read-Default {
    param([string]$Prompt, [string]$Default)
    if ($Yes) { return $Default }
    $shown = if ($Default) { "$Prompt [$Default]" } else { $Prompt }
    $v = Read-Host "  $shown"
    if ([string]::IsNullOrWhiteSpace($v)) { return $Default }
    return $v.Trim()
}

# ── 0. Docker 检查 ───────────────────────────────────────────
function Test-DockerReady {
    Write-Head '[1/5] 检查 Docker'

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Stop-WithHelp '找不到 Docker。' @(
            '本系统以 Docker 执行,请先安装 Docker Desktop:'
            ''
            '  方式一(最快,系统内置的软件包管理员):'
            '    winget install Docker.DockerDesktop'
            ''
            "  方式二:到官网下载安装"
            '    https://docs.docker.com/desktop/install/windows-install/'
            ''
            '安装完成后请「重新开机」,并确认 Docker Desktop 已启动(工作列鲸鱼图示),'
            '然后重新执行本脚本。'
        )
    }

    # docker 指令在、但引擎没跑,是最常见的情况——错误消息一长串英文,先拦下来讲人话
    if (-not (Invoke-Native docker @('info')).Ok) {
        Stop-WithHelp 'Docker 已安装,但引擎没有在执行。' @(
            '请从「开始」功能表开启 Docker Desktop,等工作列的鲸鱼图示不再转动'
            '(左下角显示 Engine running),再重新执行本脚本。'
            ''
            '若刚装好还没重开机,请先重开机。'
        )
    }

    $v = (Invoke-Native docker @('version', '--format', '{{.Server.Version}}')).Output
    Write-Ok "Docker 引擎执行中(版本 $v)"

    if (-not (Invoke-Native docker @('compose', 'version')).Ok) {
        Stop-WithHelp '这个 Docker 没有 Compose 外挂。' @(
            '请升级 Docker Desktop 到近期版本(内置 Compose v2)。'
        )
    }
    Write-Ok 'Docker Compose 可用'
}

# ── 1. 目录与配置文件 ──────────────────────────────────────────
function Get-InstallDir {
    Write-Head '[2/5] 准备安装目录'

    if (-not (Test-Path $InstallPath)) {
        $null = New-Item -ItemType Directory -Path $InstallPath -Force
        Write-Ok "已建立 $InstallPath"
    }
    else {
        Write-Ok "使用既有目录 $InstallPath"
    }
    return (Resolve-Path $InstallPath).Path
}

# compose 的项目名称决定「哪些容器与 volume 属于同一套」。默认写死在
# docker-compose.yml 的 name: scheduling,可由 .env 的 COMPOSE_PROJECT_NAME 盖过。
function Resolve-ProjectName([string]$Dir) {
    if ($ProjectName) {
        if ($ProjectName -notmatch '^[a-z0-9][a-z0-9_-]*$') {
            Stop-WithHelp "项目名称「$ProjectName」不合法。" @(
                'Docker 要求:只能用小写英数字、底线与连字符,且开头须为英数字。'
                '例如:scheduling-test'
            )
        }
        return $ProjectName
    }
    $envFile = Join-Path $Dir '.env'
    if (Test-Path $envFile) {
        foreach ($l in [System.IO.File]::ReadAllLines($envFile)) {
            if ($l -match '^COMPOSE_PROJECT_NAME="?([^"\s]+)"?') { return $Matches[1] }
        }
    }
    return 'scheduling'   # 与 docker-compose.yml 的 name: 一致
}

# 同名项目若指向别的目录,docker compose up 会直接接管那一套——包含它的数据库 volume。
# 这是本脚本唯一可能毁掉既有数据的路径,所以挡在启动之前。
function Assert-NoProjectConflict([string]$Dir, [string]$Project) {
    # 千万别用 --format '{{.Label "…"}}':PowerShell 5.1 传给原生程序时会把内层引号
    # 吃掉,docker 收到残缺的 template 直接报错,于是这道检查会「静默失效」——
    # 看起来一切正常,实际上完全没在挡。踩过一次,改用不含引号的 compose ls。
    $r = Invoke-Native docker @('compose', 'ls', '--all', '--format', 'json')
    if (-not $r.Ok -or -not $r.Output) {
        Write-Attn '无法列出既有的 docker compose 项目,跳过重复安装检查。'
        return
    }
    # 这里的写法有讲究:PS 5.1 的 ConvertFrom-Json 会把整个 JSON 阵列当成「一个」
    # 管道项目提交,所以 @($x | ConvertFrom-Json) 得到的是 1 个元素(内含全部项目),
    # 后续逐一比对永远不相等——这道检查就静默失效了。必须先指派再 @() 展开。
    try {
        $parsed = $r.Output | ConvertFrom-Json
        $projects = @($parsed)
    }
    catch {
        Write-Attn '无法解析 docker compose 项目列表,跳过重复安装检查。'
        return
    }

    $mine = Join-Path $Dir 'docker-compose.yml'
    $others = @()
    foreach ($p in $projects) {
        if ($p.Name -ne $Project) { continue }
        if ($p.PSObject.Properties.Name -notcontains 'ConfigFiles') { continue }
        foreach ($cfg in ([string]$p.ConfigFiles -split ',')) {
            $c = $cfg.Trim()
            # PowerShell 的 -ne 对字串默认不分大小写,正好符合 Windows 路径语意
            if ($c -and ($c -ne $mine)) { $others += $c }
        }
    }
    $others = @($others | Select-Object -Unique)
    if ($others.Count -eq 0) { return }

    Write-Host ''
    Write-Attn "这台主机上已经有一套名为「$Project」的部署,但它在别的文件夹:"
    foreach ($o in $others) { Write-Note "  $o" }
    Write-Host ''
    Write-Attn '继续下去会「接管」那一套,而不是另外装一套新的——'
    Write-Attn '它的容器会被依这里的设置重建,数据库 volume 也是同一份。'
    Write-Host ''
    Write-Note '若你要的是「再装一套独立的测试环境」,请改用不同的项目名称重跑,例如:'
    Write-Note '  .\install.ps1 -ProjectName scheduling-test -InstallPath D:\scheduling-test'
    Write-Host ''

    if ($Yes) {
        Stop-WithHelp '为避免误覆盖既有部署,-Yes 模式下不接管别的目录。' @(
            '请加上 -ProjectName 指定新名称,或移除 -Yes 以交互方式确认。'
        )
    }
    $a = Read-Host '  确定要接管既有的那一套吗?(输入 yes 继续,其他任意键取消)'
    if ($a -ne 'yes') { Write-Host ''; Write-Host '  已取消。' -ForegroundColor Yellow; exit 0 }
}

function Save-RemoteFile {
    param([string]$Url, [string]$Dest)
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    }
    catch {
        Stop-WithHelp "下载失败:$Url" @(
            "错误:$($_.Exception.Message)"
            ''
            '请确认这台主机能连上互联网(GitHub)。若学校网络有防火墙或 Proxy,'
            '可改成手动下载下列两个文件,放进安装目录后,加上 -SkipStart 重跑本脚本:'
            "  $RawBase/docker-compose.yml"
            "  $RawBase/.env.example"
        )
    }
}

# ── 2. 生成 .env ─────────────────────────────────────────────
function New-SecretKey {
    # 用 .NET 的密码学乱数。Windows 没有内置 openssl,原文件的 openssl rand 在此无法执行
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return (($bytes | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Read-AdminPassword {
    while ($true) {
        $s1 = Read-Host '  管理员密码(输入时不会显示)' -AsSecureString
        $p1 = ConvertFrom-SecureStringPlain $s1
        if ($p1.Length -lt 8) { Write-Attn '至少 8 个字符,请重新输入。'; continue }
        if ($p1 -match '["\\]') { Write-Attn '请避免使用 " 与 \ 这两个字符。'; continue }
        $s2 = Read-Host '  再输入一次确认' -AsSecureString
        if ($p1 -ne (ConvertFrom-SecureStringPlain $s2)) { Write-Attn '两次输入不一致,请重来。'; continue }
        return $p1
    }
}

function ConvertFrom-SecureStringPlain([System.Security.SecureString]$s) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

function Test-PortFree([int]$p) {
    try {
        $used = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
        return ($null -eq $used)
    }
    catch { return $true }   # 旧系统没有这个 cmdlet,就别挡用户
}

function Resolve-Port {
    if ($Port) {
        if (-not (Test-PortFree $Port)) { Write-Attn "端口号 $Port 目前已被占用,启动可能失败。" }
        return $Port
    }
    $candidate = 80
    if (-not (Test-PortFree 80)) {
        Write-Attn '端口号 80 已被其他程序占用(常见于 IIS、Skype 或另一套 Web 服务)。'
        $candidate = 8080
        while (-not (Test-PortFree $candidate) -and $candidate -lt 8100) { $candidate++ }
        Write-Note "改用 $candidate。往后访问地址要多带端口号,例如 http://主机IP:$candidate"
    }
    while ($true) {
        $answer = Read-Default '对外连接端口' $candidate
        $parsed = 0
        if ([int]::TryParse($answer, [ref]$parsed) -and $parsed -ge 1 -and $parsed -le 65535) {
            return $parsed
        }
        Write-Attn '请输入 1–65535 之间的数字。'
    }
}

function Resolve-HttpsPort {
    # compose 是「无条件」发布 443 的,即使你根本没启用 HTTPS。
    # 443 被别的服务占著时,web 容器会起不来,而 Docker 吐的错误消息只说
    # 「Bind for 0.0.0.0:443 failed」——用户完全看不出跟自己设的 80 有什么关系。
    # 这里先帮他闪开,不必为了一个没在用的端口卡住整个安装。
    if (Test-PortFree 443) { return 443 }
    $c = 8443
    while (-not (Test-PortFree $c) -and $c -lt 8500) { $c++ }
    Write-Attn "端口号 443 已被占用,HTTPS 端口改用 $c(目前走 HTTP,不影响使用)。"
    return $c
}

function Write-EnvFile {
    param([string]$Dir, [hashtable]$Values)

    # 以 .env.example 为底逐行取代,而不是自己拼一份:
    # 日后 .env.example 新增设置项时,这里会自动跟上,不会漏。
    $example = Join-Path $Dir '.env.example'
    $lines = [System.IO.File]::ReadAllLines($example, [System.Text.Encoding]::UTF8)
    $handled = @{}

    $out = foreach ($line in $lines) {
        $m = [regex]::Match($line, '^([A-Z_][A-Z0-9_]*)=')
        if ($m.Success -and $Values.ContainsKey($m.Groups[1].Value)) {
            $key = $m.Groups[1].Value
            $handled[$key] = $true
            $val = [string]$Values[$key]
            # docker compose 会对 .env 的值做变量展开,值里的 $ 必须写成 $$。
            # 不escape 的话,密码 my$ecret123 会被解读成 my + ${ecret123} 而变成 my——
            # 实测确认过,而且从头到尾没有任何错误消息,用户只会发现自己登不进去。
            $val = $val.Replace('$', '$$')
            # 含中文或空白的值加引号(校名、密码);纯数字/十六进位不加,避免被当字串
            if ($val -match '^[A-Za-z0-9_.:\/-]+$') { "$key=$val" } else { "$key=`"$val`"" }
        }
        else { $line }
    }

    # .env.example 里是注解掉的项目(如 HTTPS_PORT)不会被上面比对到,补在档尾
    $extra = foreach ($key in ($Values.Keys | Where-Object { -not $handled.ContainsKey($_) } | Sort-Object)) {
        $val = ([string]$Values[$key]).Replace('$', '$$')
        if ($val -match '^[A-Za-z0-9_.:\/-]+$') { "$key=$val" } else { "$key=`"$val`"" }
    }
    if ($extra) {
        $out = @($out) + @('', '# ── 由安装程序加入 ──────────────────') + @($extra)
    }

    # 关键:UTF-8 但「不加 BOM」。加了 BOM,docker compose 读 .env 时
    # 第一个变量名会变成「\ufeffADMIN_USERNAME」而读不到。记事本另存很容易踩到。
    $dest = Join-Path $Dir '.env'
    [System.IO.File]::WriteAllText($dest, (($out -join "`n") + "`n"),
        (New-Object System.Text.UTF8Encoding $false))
}

# ── 3. 启动 ──────────────────────────────────────────────────
function Start-Stack([string]$Dir, [int]$p) {
    Write-Head '[4/5] 下载映像并启动(首次约需数分钟)'
    Push-Location $Dir
    # docker 把下载进度写在 stderr。用户若把整个脚本的输出导向文件存记录
    # (.\install.ps1 > log.txt 2>&1),PS 5.1 会把那些进度行当成致命错误而中断安装。
    # 这里改用退出码判断成败,不让 stderr 决定生死。
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        Write-Step '下载官方映像…'
        & docker compose pull
        if ($LASTEXITCODE -ne 0) {
            Stop-WithHelp '映像下载失败。' @(
                '常见原因:网络不通、或学校防火墙阻止 ghcr.io。'
                '可改用「从源代码构建」的方式,见安装指南。'
            )
        }

        Write-Step '启动六个容器…'
        & docker compose up -d --wait --wait-timeout 300
        if ($LASTEXITCODE -ne 0) {
            & docker compose ps
            Stop-WithHelp '容器启动未成功。' @(
                "请在 $Dir 执行下列指令查看原因:"
                '  docker compose logs --tail 50'
                ''
                '若错误消息提到 "port is already allocated",是端口号被占用:'
                '改 .env 的 HTTP_PORT(网页端口)或 HTTPS_PORT(即使没用 HTTPS 也会被占用),'
                '然后重跑 docker compose up -d'
            )
        }
    }
    finally {
        $ErrorActionPreference = $prevEap
        Pop-Location
    }

    Write-Step '确认系统响应…'
    $ok = $false
    foreach ($attempt in 1..30) {
        try {
            $r = Invoke-WebRequest "http://localhost:$p/api/health" -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { $ok = $true; break }
        }
        catch { }
        Start-Sleep -Seconds 2
    }
    if ($ok) { Write-Ok '系统已可用' }
    else { Write-Attn '容器起来了,但健康检查没过。稍等一分钟再开网页看看。' }
    return $ok
}

function Get-LanAddress {
    try {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object {
                $_.IPAddress -notlike '127.*' -and
                $_.IPAddress -notlike '169.254.*' -and
                # 排除 Docker / WSL / Hyper-V 的虚拟网卡,那些地址校内其他电脑连不到
                $_.InterfaceAlias -notlike '*Loopback*' -and
                $_.InterfaceAlias -notlike 'vEthernet*' -and
                $_.InterfaceAlias -notlike '*WSL*' -and
                $_.InterfaceAlias -notlike '*Docker*'
            } |
            Sort-Object -Property InterfaceMetric |
            Select-Object -First 1
        if ($ip) { return $ip.IPAddress }
    }
    catch { }
    return $null
}

# ══ 主流程 ═══════════════════════════════════════════════════
Write-Host ''
Write-Host '  学校排课、调课与代课管理系统 · 安装程序' -ForegroundColor Cyan
Write-Host '  ─────────────────────────────' -ForegroundColor DarkGray
Write-Host '  数据全部留在这台主机,不会上传到任何地方。' -ForegroundColor DarkGray

Test-DockerReady
$dir = Get-InstallDir
$project = Resolve-ProjectName $dir
Assert-NoProjectConflict -Dir $dir -Project $project

Write-Head '[3/5] 获取配置文件'
Save-RemoteFile "$RawBase/docker-compose.yml" (Join-Path $dir 'docker-compose.yml')
Save-RemoteFile "$RawBase/.env.example"       (Join-Path $dir '.env.example')
Write-Ok '已下载 docker-compose.yml 与 .env.example'

$envPath = Join-Path $dir '.env'
$needConfig = $true
if ((Test-Path $envPath) -and -not $Reconfigure) {
    Write-Attn '检测到既有的 .env,保留原设置(校名、密码、密钥都不动)。'
    Write-Note '要重新设置请加参数 -Reconfigure 重跑。'
    $needConfig = $false
}

if ($needConfig) {
    Write-Host ''
    Write-Host '  请回答三个问题(直接按 Enter 即采用默认值):' -ForegroundColor Cyan
    Write-Host ''

    $school = if ($SchoolName) { $SchoolName } else { Read-Default '学校名称(显示在界面与课表上)' '海州市启明实验初级中学' }

    if ($AdminPassword) {
        # 走参数的路径同样要挡:交互输入那边挡了,这边不阻止就成了漏洞
        if ($AdminPassword.Length -lt 8) { Stop-WithHelp '-AdminPassword 至少需 8 个字符。' @() }
        if ($AdminPassword -match '["\\]') { Stop-WithHelp '-AdminPassword 不可含 " 或 \ 字符。' @() }
        $pw = $AdminPassword
    }
    elseif ($Yes) { Stop-WithHelp '-Yes 需要同时提供 -AdminPassword。' @() }
    else {
        Write-Note '管理员账号固定为 admin,首次登录后系统会要求你再改一次密码。'
        $pw = Read-AdminPassword
    }

    $chosenPort = Resolve-Port

    $values = @{
        ADMIN_USERNAME = 'admin'
        ADMIN_PASSWORD = $pw
        SCHOOL_NAME    = $school
        TZ             = $TimeZone
        SECRET_KEY     = (New-SecretKey)
        HTTP_PORT      = $chosenPort
        HTTPS_PORT     = (Resolve-HttpsPort)
        IMAGE_TAG      = $ImageTag
    }
    # 只在非默认时写入:留白的话就沿用 docker-compose.yml 里的 name: scheduling
    if ($project -ne 'scheduling') { $values['COMPOSE_PROJECT_NAME'] = $project }

    Write-EnvFile -Dir $dir -Values $values
    Write-Ok "已写入 $envPath(含自动生成的 SECRET_KEY)"
    if ($project -ne 'scheduling') { Write-Note "此部署的项目名称为 $project(记在 .env,后续指令会自动沿用)" }
    Write-Note '这个文件含有密码,请勿上传到云端硬盘或 GitHub。'
}

# 读回实际生效的端口号(保留既有 .env 的情况下,端口号以文件里的为准)
$activePort = 80
foreach ($l in [System.IO.File]::ReadAllLines($envPath)) {
    if ($l -match '^HTTP_PORT="?(\d+)"?') { $activePort = [int]$Matches[1] }
}

if ($SkipStart) {
    Write-Head '已生成配置文件,依 -SkipStart 未启动'
    Write-Note "检查无误后,在 $dir 执行:docker compose up -d"
    Write-Host ''
    exit 0
}

$healthy = Start-Stack -Dir $dir -p $activePort

# ── 4. 完成 ──────────────────────────────────────────────────
$suffix = if ($activePort -eq 80) { '' } else { ":$activePort" }
$lan = Get-LanAddress

Write-Head '[5/5] 安装完成'
Write-Host ''
Write-Host '  在这台主机上开:' -ForegroundColor White
Write-Host "    http://localhost$suffix" -ForegroundColor Green
if ($lan) {
    Write-Host '  校内其他电脑开:' -ForegroundColor White
    Write-Host "    http://$lan$suffix" -ForegroundColor Green
    Write-Note '(若连不到,多半是这台主机的 Windows 防火墙阻止,需放行该端口号)'
}
Write-Host ''
Write-Host '  账号 admin,密码是你刚才设置的那组;登录后会要求改一次密码,' -ForegroundColor White
Write-Host '  然后进入「设置精灵」,照画面五个步骤建立学期、教师、班级、科目。' -ForegroundColor White
Write-Host ''
Write-Note "安装目录:$dir"
Write-Note "停止:docker compose down    重新启动:docker compose up -d(需先 cd 到上面的目录)"
Write-Note "操作手册与部署文件:$RepoUrl"
Write-Host ''

if ($healthy -and -not $Yes) { Start-Process "http://localhost$suffix" }
