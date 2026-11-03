@echo off
rem Windows launcher for the WeChat notifier.
rem Usage: scripts\wechat-notify.cmd status
rem        scripts\wechat-notify.cmd send "hi"
rem Set WECHAT_NOTIFY_PYTHON to use a specific interpreter.
setlocal
set "HERE=%~dp0"
if defined WECHAT_NOTIFY_PYTHON (
  set "PY=%WECHAT_NOTIFY_PYTHON%"
) else (
  set "PY=python"
)
"%PY%" "%HERE%wechat_notify.py" %*
exit /b %ERRORLEVEL%
