# Screenshot on Windows WITHOUT injecting any input event.
#
# How it reads the screen:
#   screen 模式 -> System.Drawing.Graphics.CopyFromScreen (GDI BitBlt, read-only)
#   window 模式 -> user32 PrintWindow (render the window into a memory DC)
# Neither path calls SendInput / SendKeys / mouse_event / keybd_event, sets a
# hook, or moves the cursor, so it does not generate keyboard/mouse events and
# does not steal focus.
#
# What it cannot capture (OS limits, not our choice):
#   - DRM/protected content (some video players) -> black frame
#   - the UAC secure desktop, the lock screen, Ctrl+Alt+Del screen
#   - truly minimized windows in screen mode (use -Mode window for those)
#
# Examples:
#   .\screenshot.ps1                          # whole virtual screen -> shot-<ts>.png
#   .\screenshot.ps1 -Out .\dsh.png
#   .\screenshot.ps1 -Mode window -WindowTitle "DeepSeek Harness"
#   .\screenshot.ps1 -Format jpeg -Quality 85 -MaxWidth 1600

[CmdletBinding()]
param(
    [string]$Out,
    [ValidateSet('screen', 'window')][string]$Mode = 'screen',
    [string]$WindowTitle,
    [ValidateSet('png', 'jpeg')][string]$Format = 'png',
    [int]$Quality = 85,
    [int]$MaxWidth = 0,
    [switch]$Quiet
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

# Make this process DPI-aware so we capture real pixels, not a scaled bitmap.
# (Also a pure API call - no input events.)
try {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class SnapshotNative {
    [StructLayout(LayoutKind.Sequential)]
    public struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint flags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@ -ErrorAction Stop
    [void][SnapshotNative]::SetProcessDPIAware()
} catch {
    # Already loaded or unavailable: capture still works, just may be DPI-scaled.
}

# Milliseconds since the last keyboard/mouse input (system-wide).
# If the capture injected any input event, this counter would reset to ~0.
function Get-IdleMilliseconds {
    try {
        $info = New-Object SnapshotNative+LASTINPUTINFO
        $info.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($info)
        if (-not [SnapshotNative]::GetLastInputInfo([ref]$info)) { return $null }
        $tick = [Environment]::TickCount
        $ms = ($tick - [long]$info.dwTime) -band 0xFFFFFFFF
        return [long]$ms
    } catch { return $null }
}

if (-not $Out) {
    $Out = Join-Path $PSScriptRoot ("shot-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + "." + $Format)
}
$Out = [System.IO.Path]::GetFullPath($Out)
$dir = [System.IO.Path]::GetDirectoryName($Out)
if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

$cursorBefore = [System.Windows.Forms.Cursor]::Position
$idleBefore = Get-IdleMilliseconds

$bmp = $null
$graphics = $null
try {
    if ($Mode -eq 'screen') {
        $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
        if ($bounds.Width -le 0 -or $bounds.Height -le 0) { throw "virtual screen has no area" }
        $bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $graphics = [System.Drawing.Graphics]::FromImage($bmp)
        $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size,
            [System.Drawing.CopyPixelOperation]::SourceCopy)
        $sourceNote = "virtual screen $($bounds.Width)x$($bounds.Height) at $($bounds.X),$($bounds.Y)"
    }
    else {
        if (-not $WindowTitle) { throw "window mode needs -WindowTitle" }
        $proc = Get-Process | Where-Object {
            $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like "*$WindowTitle*"
        } | Select-Object -First 1
        if (-not $proc) { throw "no visible top-level window whose title contains '$WindowTitle'" }
        $hwnd = $proc.MainWindowHandle
        $rect = New-Object SnapshotNative+RECT
        if (-not [SnapshotNative]::GetWindowRect($hwnd, [ref]$rect)) { throw "GetWindowRect failed" }
        $w = $rect.Right - $rect.Left
        $h = $rect.Bottom - $rect.Top
        if ($w -le 0 -or $h -le 0) { throw "window has no area" }
        # 2 = PW_RENDERFULLCONTENT: capture DWM-composited content without activating the window.
        $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $graphics = [System.Drawing.Graphics]::FromImage($bmp)
        $hdc = $graphics.GetHdc()
        try {
            $ok = [SnapshotNative]::PrintWindow($hwnd, $hdc, 2)
        }
        finally {
            $graphics.ReleaseHdc($hdc)
        }
        if (-not $ok) {
            # Some apps refuse PrintWindow; fall back to copying that screen region.
            $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0,
                (New-Object System.Drawing.Size($w, $h)),
                [System.Drawing.CopyPixelOperation]::SourceCopy)
        }
        $sourceNote = "window '$($proc.MainWindowTitle)' ${w}x${h}"
    }

    if ($MaxWidth -gt 0 -and $bmp.Width -gt $MaxWidth) {
        $ratio = $MaxWidth / $bmp.Width
        $resized = New-Object System.Drawing.Bitmap($MaxWidth, [int][Math]::Round($bmp.Height * $ratio))
        $resizeGraphics = [System.Drawing.Graphics]::FromImage($resized)
        $resizeGraphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $resizeGraphics.DrawImage($bmp, 0, 0, $resized.Width, $resized.Height)
        $resizeGraphics.Dispose()
        $bmp.Dispose()
        $bmp = $resized
    }

    if ($Format -eq 'jpeg') {
        $encoder = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() |
            Where-Object { $_.MimeType -eq 'image/jpeg' } | Select-Object -First 1
        $encoderParams = New-Object System.Drawing.Imaging.EncoderParameters(1)
        $encoderParams.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter(
            [System.Drawing.Imaging.Encoder]::Quality, [long]$Quality)
        $bmp.Save($Out, $encoder, $encoderParams)
        $encoderParams.Dispose()
    }
    else {
        $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    }
}
finally {
    if ($graphics) { $graphics.Dispose() }
    if ($bmp) { $bmp.Dispose() }
}

$cursorAfter = [System.Windows.Forms.Cursor]::Position
$idleAfter = Get-IdleMilliseconds
$info = [System.IO.FileInfo]$Out

if (-not $Quiet) {
    [pscustomobject]@{
        Path         = $info.FullName
        Bytes        = $info.Length
        Source       = $sourceNote
        IdleBeforeMs = $idleBefore
        IdleAfterMs  = $idleAfter
        # Idle time kept growing across the capture => the script itself injected
        # no keyboard/mouse input. A reset to ~0 while capturing would mean input.
        NoInjectedInput = if ($null -ne $idleBefore -and $null -ne $idleAfter) { ($idleAfter -ge $idleBefore) } else { 'unknown' }
        CursorBefore = "$($cursorBefore.X),$($cursorBefore.Y)"
        CursorAfter  = "$($cursorAfter.X),$($cursorAfter.Y)"
        CursorMoved  = ($cursorBefore -ne $cursorAfter)
    } | Format-List
}
