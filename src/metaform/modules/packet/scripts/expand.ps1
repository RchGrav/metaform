# Expand one variation of a packet into the work it stands for.
#
#   expand.ps1 -Origin <origin folder> -Variation <variation folder> -Output <output folder>
#
# The variation holds changes.diff, a diff of the text that differs from the origin; files\, a whole copy of each
# binary file that differs; and removed.txt, the files the work no longer has. Each part of the diff applies at the
# lines it names or not at all: when the origin is not the one the diff was taken from, this stops and names the
# file. It runs in Windows PowerShell 5.1 and in PowerShell 7, and needs nothing else.
param(
  [Parameter(Mandatory = $true)][string]$Origin,
  [Parameter(Mandatory = $true)][string]$Variation,
  [Parameter(Mandatory = $true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$Mark = '\ No newline at end of file'
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Stop-Expanding([string]$Message) {
  [Console]::Error.WriteLine($Message)
  exit 1
}

# A path from the packet stays inside the output folder: it is never absolute and never climbs out.
function Test-Inside([string]$Path) {
  if ($Path -eq '' -or $Path.StartsWith('/') -or $Path.StartsWith('\') -or $Path.Contains(':')) { return $false }
  foreach ($part in $Path.Split([char[]]@('/', '\'))) {
    if ($part -eq '..' -or $part -eq '.') { return $false }
  }
  return $true
}

# The lines of a file, and whether its last line has no newline after it.
function Read-Lines([string]$File) {
  $text = [System.IO.File]::ReadAllText($File, $Utf8)
  $lines = New-Object 'System.Collections.Generic.List[string]'
  $bare = $false
  if ($text.Length -gt 0) {
    $lines.AddRange([string[]]$text.Split("`n"))
    if ($lines[$lines.Count - 1] -eq '') { $lines.RemoveAt($lines.Count - 1) } else { $bare = $true }
  }
  return @{ Lines = $lines; Bare = $bare }
}

if (-not (Test-Path -LiteralPath $Origin -PathType Container)) { Stop-Expanding "No origin folder at $Origin." }
if (-not (Test-Path -LiteralPath $Variation -PathType Container)) { Stop-Expanding "No variation folder at $Variation." }
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$Origin = (Resolve-Path -LiteralPath $Origin).Path
$Variation = (Resolve-Path -LiteralPath $Variation).Path
$Output = (Resolve-Path -LiteralPath $Output).Path
Get-ChildItem -LiteralPath $Origin -Force | Copy-Item -Destination $Output -Recurse -Force

$changes = Join-Path $Variation 'changes.diff'
if ((Test-Path -LiteralPath $changes) -and ((Get-Item -LiteralPath $changes).Length -gt 0)) {
  $diff = (Read-Lines $changes).Lines
  $at = 0
  while ($at -lt $diff.Count) {
    if (-not $diff[$at].StartsWith('--- ') -or ($at + 1 -ge $diff.Count) -or -not $diff[$at + 1].StartsWith('+++ b/')) {
      $at++
      continue
    }
    $based = $diff[$at].Substring(4) -cne '/dev/null'
    $path = $diff[$at + 1].Substring(6)
    if (-not (Test-Inside $path)) { Stop-Expanding "$path is outside the work." }
    $at += 2
    $old = New-Object 'System.Collections.Generic.List[string]'
    $bare = $false
    if ($based) {
      $source = Join-Path $Origin $path
      if (-not (Test-Path -LiteralPath $source)) { Stop-Expanding "$path is not as it was when the diff was taken." }
      $read = Read-Lines $source
      $old = $read.Lines
      $bare = $read.Bare
    }
    $new = New-Object 'System.Collections.Generic.List[string]'
    $from = 0
    $open = $false
    while (($at -lt $diff.Count) -and $diff[$at].StartsWith('@@ -')) {
      $part = $diff[$at].Split(' ')
      $was = $part[1].Substring(1).Split(',')
      $now = $part[2].Substring(1).Split(',')
      $start = [int]$was[0]
      $needOld = 1
      if ($was.Count -gt 1) { $needOld = [int]$was[1] }
      $needNew = 1
      if ($now.Count -gt 1) { $needNew = [int]$now[1] }
      $to = $start
      if ($needOld -gt 0) { $to = $start - 1 }
      if (($to -lt $from) -or ($to -gt $old.Count)) { Stop-Expanding "$path is not as it was when the diff was taken." }
      while ($from -lt $to) {
        $new.Add($old[$from])
        $open = $bare -and ($from -eq $old.Count - 1)
        $from++
      }
      $at++
      while (($needOld -gt 0) -or ($needNew -gt 0) -or (($at -lt $diff.Count) -and ($diff[$at] -ceq $Mark))) {
        $line = $diff[$at]
        if ($line -ceq $Mark) { $at++; continue }
        $unended = ($at + 1 -lt $diff.Count) -and ($diff[$at + 1] -ceq $Mark)
        $kind = $line.Substring(0, 1)
        $text = $line.Substring(1)
        if ($kind -eq '+') {
          $new.Add($text)
          $open = $unended
          $needNew--
        } else {
          $last = $bare -and ($from -eq $old.Count - 1)
          if (($from -ge $old.Count) -or ($old[$from] -cne $text) -or ($last -ne $unended)) {
            Stop-Expanding "$path is not as it was when the diff was taken."
          }
          if ($kind -eq ' ') {
            $new.Add($text)
            $open = $unended
            $needNew--
          }
          $from++
          $needOld--
        }
        $at++
      }
    }
    while ($from -lt $old.Count) {
      $new.Add($old[$from])
      $open = $bare -and ($from -eq $old.Count - 1)
      $from++
    }
    $target = Join-Path $Output $path
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    $text = [string]::Join("`n", $new.ToArray())
    if (($new.Count -gt 0) -and -not $open) { $text += "`n" }
    [System.IO.File]::WriteAllText($target, $text, $Utf8)
  }
}

$whole = Join-Path $Variation 'files'
if (Test-Path -LiteralPath $whole -PathType Container) {
  Get-ChildItem -LiteralPath $whole -Force | Copy-Item -Destination $Output -Recurse -Force
}

$removed = Join-Path $Variation 'removed.txt'
if (Test-Path -LiteralPath $removed) {
  foreach ($path in (Read-Lines $removed).Lines) {
    if ($path -eq '') { continue }
    if (-not (Test-Inside $path)) { Stop-Expanding "$path is outside the work." }
    $gone = Join-Path $Output $path
    if (Test-Path -LiteralPath $gone -PathType Leaf) { Remove-Item -LiteralPath $gone -Force }
  }
}
Write-Output "Expanded into $Output"
