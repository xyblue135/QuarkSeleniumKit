param(
    [string]$WindowTitle = "",
    [int]$IntervalSeconds = 1,
    [switch]$TopMost,
    [switch]$Once,
    [switch]$KeepHistory,
    [string]$OutputName = "",
    [ValidateRange(0,100)][int]$XStartPct = 0,
    [ValidateRange(0,100)][int]$XEndPct = 100,
    [ValidateRange(0,100)][int]$YStartPct = 0,
    [ValidateRange(0,100)][int]$YEndPct = 100
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class Win32WindowCapture {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
}
"@
function Get-SafeFileName {
    param([string]$Name)
    $invalid = [System.IO.Path]::GetInvalidFileNameChars()
    $safe = $Name.Trim()
    foreach ($char in $invalid) {
        $safe = $safe.Replace($char, "_")
    }
    $safe = $safe -replace "\s+", " "
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return "window"
    }
    return $safe
}
function Get-VisibleWindows {
    $windows = New-Object System.Collections.Generic.List[object]
    $callback = [Win32WindowCapture+EnumWindowsProc]{
        param([IntPtr]$hWnd, [IntPtr]$lParam)
        if (-not [Win32WindowCapture]::IsWindowVisible($hWnd)) {
            return $true
        }
        $length = [Win32WindowCapture]::GetWindowTextLength($hWnd)
        if ($length -le 0) {
            return $true
        }
        $builder = New-Object System.Text.StringBuilder ($length + 1)
        [void][Win32WindowCapture]::GetWindowText($hWnd, $builder, $builder.Capacity)
        $title = $builder.ToString().Trim()
        if ([string]::IsNullOrWhiteSpace($title)) {
            return $true
        }
        $rect = New-Object Win32WindowCapture+RECT
        if (-not [Win32WindowCapture]::GetWindowRect($hWnd, [ref]$rect)) {
            return $true
        }
        $width = $rect.Right - $rect.Left
        $height = $rect.Bottom - $rect.Top
        if ($width -le 0 -or $height -le 0) {
            return $true
        }
        $processName = ""
        try {
            $processId = 0
            [void][Win32WindowCapture]::GetWindowThreadProcessId($hWnd, [ref]$processId)
            if ($processId -gt 0) {
                $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
                $processName = $process.ProcessName
            }
        } catch {
            $processName = ""
        }
        $windows.Add([pscustomobject]@{
            Handle = $hWnd
            Title = $title
            ProcessName = $processName
            Width = $width
            Height = $height
        })
        return $true
    }
    [void][Win32WindowCapture]::EnumWindows($callback, [IntPtr]::Zero)
    return $windows | Sort-Object Title
}
function Select-Window {
    param([string]$Title)
    $windows = @(Get-VisibleWindows)
    if ($windows.Count -eq 0) {
        throw "No visible windows were found."
    }
    if (-not [string]::IsNullOrWhiteSpace($Title)) {
        $matches = @($windows | Where-Object {
            $_.Title.IndexOf($Title, [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $_.ProcessName.IndexOf($Title, [StringComparison]::OrdinalIgnoreCase) -ge 0
        })
        if ($matches.Count -eq 1) {
            return $matches[0]
        }
        if ($matches.Count -gt 1) {
            Write-Host "Multiple windows matched '$Title':"
            for ($i = 0; $i -lt $matches.Count; $i++) {
                Write-Host ("[{0}] {1} ({2}) {3}x{4}" -f ($i + 1), $matches[$i].Title, $matches[$i].ProcessName, $matches[$i].Width, $matches[$i].Height)
            }
            $choice = Read-Host "Choose a window number"
            $index = [int]$choice - 1
            if ($index -ge 0 -and $index -lt $matches.Count) {
                return $matches[$index]
            }
            throw "Invalid window selection."
        }
        throw "No visible window matched '$Title'."
    }
    Write-Host "Visible windows:"
    for ($i = 0; $i -lt $windows.Count; $i++) {
        Write-Host ("[{0}] {1} ({2}) {3}x{4}" -f ($i + 1), $windows[$i].Title, $windows[$i].ProcessName, $windows[$i].Width, $windows[$i].Height)
    }
    $choice = Read-Host "Choose a window number"
    $index = [int]$choice - 1
    if ($index -lt 0 -or $index -ge $windows.Count) {
        throw "Invalid window selection."
    }
    return $windows[$index]
}
function Capture-Window {
    param(
        [IntPtr]$Handle,
        [string]$Path,
        [switch]$MakeTopMost,
        [int]$XStartPct,
        [int]$XEndPct,
        [int]$YStartPct,
        [int]$YEndPct
    )
    $SW_RESTORE = 9
    $HWND_TOPMOST = [IntPtr]::new(-1)
    $SWP_NOSIZE = 0x0001
    $SWP_NOMOVE = 0x0002
    $SWP_SHOWWINDOW = 0x0040
    [void][Win32WindowCapture]::ShowWindow($Handle, $SW_RESTORE)
    if ($MakeTopMost) {
        [void][Win32WindowCapture]::SetWindowPos($Handle, $HWND_TOPMOST, 0, 0, 0, 0, $SWP_NOMOVE -bor $SWP_NOSIZE -bor $SWP_SHOWWINDOW)
    }
    [void][Win32WindowCapture]::SetForegroundWindow($Handle)
    Start-Sleep -Milliseconds 300
    $rect = New-Object Win32WindowCapture+RECT
    if (-not [Win32WindowCapture]::GetWindowRect($Handle, [ref]$rect)) {
        throw "Failed to read window rectangle."
    }
    $winW = $rect.Right - $rect.Left
    $winH = $rect.Bottom - $rect.Top
    if ($winW -le 0 -or $winH -le 0) {
        throw "Window has an invalid size: ${winW}x${winH}."
    }

    # 按百分比计算裁剪区域
    $srcX = [int]($winW * $XStartPct / 100.0)
    $srcY = [int]($winH * $YStartPct / 100.0)
    $srcW = [int]($winW * ($XEndPct - $XStartPct) / 100.0)
    $srcH = [int]($winH * ($YEndPct - $YStartPct) / 100.0)

    # 边界保护
    if($srcW -le 0){$srcW=1}
    if($srcH -le 0){$srcH=1}

    $fullBmp = New-Object System.Drawing.Bitmap $winW, $winH
    $gFull = [System.Drawing.Graphics]::FromImage($fullBmp)
    try {
        $gFull.CopyFromScreen($rect.Left, $rect.Top, 0, 0, [System.Drawing.Size]::new($winW, $winH))
        # 裁剪出新位图
        $cropBmp = New-Object System.Drawing.Bitmap $srcW, $srcH
        $gCrop = [System.Drawing.Graphics]::FromImage($cropBmp)
        try{
            $gCrop.DrawImage($fullBmp, 0,0,$srcX,$srcY,$srcW,$srcH,[System.Drawing.GraphicsUnit]::Pixel)
            $cropBmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        }finally{
            $gCrop.Dispose()
            $cropBmp.Dispose()
        }
    } finally {
        $gFull.Dispose()
        $fullBmp.Dispose()
    }
}

# 参数合法性校验
if($XStartPct -ge $XEndPct){throw "XStartPct 必须小于 XEndPct"}
if($YStartPct -ge $YEndPct){throw "YStartPct 必须小于 YEndPct"}

$selected = Select-Window -Title $WindowTitle
# 截屏脚本在 powershell/ 内，上级目录才是项目根，图片统一写到 项目根/images
$imagesDir = Join-Path $PSScriptRoot ".." "images"
if (-not (Test-Path -LiteralPath $imagesDir)) {
    New-Item -ItemType Directory -Path $imagesDir | Out-Null
}
$baseName = if ([string]::IsNullOrWhiteSpace($OutputName)) { $selected.Title } else { $OutputName }
$baseName = Get-SafeFileName -Name $baseName
if ($baseName.EndsWith(".png", [StringComparison]::OrdinalIgnoreCase)) {
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($baseName)
}
Write-Host ("Capturing: {0}" -f $selected.Title)
Write-Host ("Crop config: X {0}%‑{1}% , Y {2}%‑{3}%" -f $XStartPct,$XEndPct,$YStartPct,$YEndPct)
Write-Host ("Output folder: {0}" -f $imagesDir)
Write-Host "Press Ctrl+C to stop."
do {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $fileName = if ($KeepHistory) { "${baseName}_${timestamp}.png" } else { "${baseName}.png" }
    $path = Join-Path $imagesDir $fileName
    Capture-Window -Handle $selected.Handle -Path $path -MakeTopMost:$TopMost `
        -XStartPct $XStartPct -XEndPct $XEndPct -YStartPct $YStartPct -YEndPct $YEndPct
    Write-Host ("[{0}] Saved {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $path)
    if ($Once) {
        break
    }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
