<#
.SYNOPSIS
    Install the wechat-notify skill for DeepSeek Harness (Windows).

.DESCRIPTION
    Copies the skill bundle (SKILL.md, src/, scripts/, plugin/) into a DSH skills
    directory and installs the Python dependencies. No credentials are copied --
    `login` has to be run once per machine because the bot token is issued to the
    WeChat account that scans the QR code.

.PARAMETER Dest
    Target directory. Defaults to $env:DSH_HOME\skills\wechat-notify, falling back
    to ~\.dsh\skills\wechat-notify.

.PARAMETER Python
    Interpreter used for the version check and `pip install`. Defaults to `python`,
    then `py`.

.PARAMETER NoDeps
    Skip `pip install` (useful when the environment is already provisioned).

.PARAMETER Force
    Overwrite an existing installation. Runtime state under scripts\state
    (credentials, queue) is preserved.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1

.EXAMPLE
    .\install.ps1 -Dest D:\tools\dsh\skills\wechat-notify -NoDeps -Force
#>
[CmdletBinding()]
param(
    [string]$Dest,
    [string]$Python,
    [switch]$NoDeps,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot

if (-not $Dest) {
    $dshHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $HOME '.dsh' }
    $Dest = Join-Path (Join-Path $dshHome 'skills') 'wechat-notify'
}
$Dest = [System.IO.Path]::GetFullPath($Dest)

Write-Host '== wechat-notify installer ==' -ForegroundColor Cyan
Write-Host "source : $source"
Write-Host "target : $Dest"

if ((Test-Path -LiteralPath $Dest) -and -not $Force) {
    throw "目标已存在：$Dest`n加 -Force 覆盖（scripts\state 里的凭据和队列会保留）。"
}

if (-not $Python) {
    foreach ($candidate in @('python', 'py')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { $Python = $command.Source; break }
    }
}
if (-not $Python) {
    throw '找不到 Python，请先安装 Python 3.10+，或用 -Python 指定解释器。'
}

$version = & $Python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$version -lt [version]'3.10') { throw "需要 Python >= 3.10，当前是 $version" }
Write-Host "python : $Python ($version)"

if (-not $NoDeps) {
    Write-Host 'deps   : 安装 wechat-openclaw-sdk / qrcode …'
    & $Python -m pip install --disable-pip-version-check -r (Join-Path $source 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install 失败（退出码 $LASTEXITCODE）" }
} else {
    Write-Host 'deps   : 已跳过（-NoDeps），记得自己装 requirements.txt'
}

New-Item -ItemType Directory -Path $Dest -Force | Out-Null
foreach ($file in @('SKILL.md', 'README.md', 'LICENSE', 'requirements.txt')) {
    Copy-Item -LiteralPath (Join-Path $source $file) -Destination $Dest -Force
}
# Copy-Item merges directories, so an existing scripts\state survives an upgrade.
foreach ($directory in @('src', 'scripts', 'plugin')) {
    Copy-Item -LiteralPath (Join-Path $source $directory) -Destination $Dest -Recurse -Force
}

$entry = Join-Path $Dest 'scripts\wechat_notify.py'
$installedVersion = & $Python $entry --version

Write-Host ''
Write-Host "已安装：$Dest" -ForegroundColor Green
Write-Host "版本  ：$installedVersion"
Write-Host ''
Write-Host '下一步：' -ForegroundColor Cyan
Write-Host "  1) 扫码登录：" -NoNewline
Write-Host " `"$Python`" `"$entry`" login"
Write-Host '  2) 在微信里给机器人发一条消息（拿 context_token），或先跑 prime 等着：'
Write-Host "     `"$Python`" `"$entry`" prime --timeout 180"
Write-Host '  3) 发一条测试：'
Write-Host "     `"$Python`" `"$entry`" send `"测试消息`""
Write-Host '  4) 看状态：'
Write-Host "     `"$Python`" `"$entry`" status"
Write-Host ''
Write-Host '重启 DSH（或新开一个会话）后，技能列表里会出现 wechat-notify。' -ForegroundColor DarkGray
Write-Host '想让每轮对话结束自动推微信，见 plugin\README.md（默认关闭）。' -ForegroundColor DarkGray
