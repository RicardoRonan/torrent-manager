# Bundle aria2c.exe for Windows builds (run on the Windows build machine).
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bin = Join-Path $here 'bin'
New-Item -ItemType Directory -Force -Path $bin | Out-Null

$url = 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip'
$tmp = Join-Path $env:TEMP 'aria2-win64.zip'
$extract = Join-Path $env:TEMP 'aria2-win64'

Write-Host "Downloading $url"
Invoke-WebRequest -Uri $url -OutFile $tmp
Remove-Item -Recurse -Force $extract -ErrorAction SilentlyContinue
Expand-Archive -Path $tmp -DestinationPath $extract -Force

$exe = Get-ChildItem $extract -Recurse -Filter 'aria2c.exe' | Select-Object -First 1
Copy-Item $exe.FullName (Join-Path $bin 'aria2c.exe') -Force

$copying = Get-ChildItem $exe.DirectoryName -Filter 'COPYING*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($copying) { Copy-Item $copying.FullName (Join-Path $bin 'COPYING-aria2') -Force }

Write-Host "Bundled: $(Join-Path $bin 'aria2c.exe')"
