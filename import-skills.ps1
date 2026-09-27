$ErrorActionPreference = "Stop"
$kit = "D:\jev-decision-kit"
$destRoot = Join-Path $kit "skills"
New-Item -ItemType Directory -Force -Path $destRoot | Out-Null

function Get-Category([string]$name) {
  $n = $name.ToLowerInvariant()
  $rules = @(
    @{ c = "router"; k = @("aas","skill-router","skill-creator","find-skills","using-agent-skills","port-external") },
    @{ c = "prompts"; k = @("prompt","yao-open") },
    @{ c = "thesis"; k = @("thesis","lunwen","literature","humanizer","scientific-writing","peer-review","research-paper") },
    @{ c = "market"; k = @("stock","spcx","ufo-watch") },
    @{ c = "docs"; k = @("meeting","minutes","docx","pdf","pptx","word-doc","xlsx","nano-pdf") },
    @{ c = "web"; k = @("browser","web-","frontend","html","figma","url-to","landing","agent-browser") },
    @{ c = "media"; k = @("video","montage","remotion","music","gif","illustration","xiaohei","audio","song") },
    @{ c = "design"; k = @("design","ppt","canvas","diagram","comic","poster","shuike") },
    @{ c = "research"; k = @("research","intelligence","knowledge","arxiv","news") },
    @{ c = "code"; k = @("code","debug","test","git","api","mcp","engineering","dev","impl","review","lint","tdd","ci-cd","python","react","flutter","android","ios","docker","devops") }
  )
  foreach ($rule in $rules) {
    foreach ($k in $rule.k) {
      if ($n.Contains($k)) { return $rule.c }
    }
  }
  return "other"
}

function Get-Description([string]$skillMd) {
  $lines = Get-Content -LiteralPath $skillMd -TotalCount 80 -Encoding UTF8
  $text = ($lines -join "`n")
  if ($text -notmatch "(?s)^---\s*\r?\n(.*?)\r?\n---") { return "" }
  $yaml = $Matches[1]
  if ($yaml -match "(?ms)^description:\s*[>|]-?\s*\r?\n(?<b>(?:[ \t].*\r?\n?)*)") {
    return (($Matches["b"] -replace "(?m)^[ \t]+","") -replace "\s+"," ").Trim()
  }
  if ($yaml -match "(?m)^description:\s*[""']?(?<b>.+?)[""']?\s*$") {
    return $Matches["b"].Trim().Trim('"').Trim("'")
  }
  return ""
}

$sources = @(
  @{ id = "cursor"; path = Join-Path $env:USERPROFILE ".cursor\skills" },
  @{ id = "openclaw-workspace"; path = Join-Path $env:USERPROFILE ".openclaw\workspace\skills" },
  @{ id = "agents"; path = Join-Path $env:USERPROFILE ".agents\skills" }
)

$seen = @{}
$copied = New-Object System.Collections.Generic.List[object]
$skipped = New-Object System.Collections.Generic.List[object]

foreach ($src in $sources) {
  if (-not (Test-Path $src.path)) { continue }
  Get-ChildItem -LiteralPath $src.path -Directory | ForEach-Object {
    $name = $_.Name
    $skillMd = Join-Path $_.FullName "SKILL.md"
    $isLink = [bool]($_.Attributes -band [IO.FileAttributes]::ReparsePoint)
    if ($isLink) {
      $skipped.Add([pscustomobject]@{ name = $name; source = $src.id; reason = "junction" })
      return
    }
    if (-not (Test-Path -LiteralPath $skillMd)) {
      $skipped.Add([pscustomobject]@{ name = $name; source = $src.id; reason = "no-skill-md" })
      return
    }
    if ($seen.ContainsKey($name)) {
      $skipped.Add([pscustomobject]@{ name = $name; source = $src.id; reason = "duplicate" })
      return
    }
    $cat = Get-Category $name
    $destParent = Join-Path $destRoot $cat
    $dest = Join-Path $destParent $name
    New-Item -ItemType Directory -Force -Path $destParent | Out-Null
    & robocopy $_.FullName $dest /E /NFL /NDL /NJH /NJS /nc /ns /np /XD node_modules .git __pycache__ .venv /XF .env .env.local .env.production | Out-Null
    if ($LASTEXITCODE -ge 8) {
      $skipped.Add([pscustomobject]@{ name = $name; source = $src.id; reason = "robocopy-$LASTEXITCODE" })
      return
    }
    $desc = ""
    try { $desc = Get-Description (Join-Path $dest "SKILL.md") } catch { $desc = "" }
    $scripts = @()
    $scriptsDir = Join-Path $dest "scripts"
    if (Test-Path $scriptsDir) {
      $scripts = @(Get-ChildItem $scriptsDir -File -Recurse | ForEach-Object { $_.FullName.Substring($dest.Length + 1) })
    }
    $seen[$name] = $src.id
    $copied.Add([pscustomobject]@{
      name = $name
      category = $cat
      source = $src.id
      path = $dest
      summary = $desc
      scripts = $scripts
    })
  }
}

$catalog = [pscustomobject]@{
  generatedAt = (Get-Date).ToString("s")
  root = $destRoot
  count = $copied.Count
  labels = [pscustomobject]@{
    router = "system-router"
    prompts = "prompts"
    thesis = "thesis-writing"
    market = "market"
    docs = "docs"
    web = "web"
    media = "media"
    design = "design"
    research = "research"
    code = "code"
    other = "other"
  }
  skills = $copied
}
$catalog | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $kit "catalog.json")
[pscustomobject]@{
  copied = $copied.Count
  skipped = $skipped
} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $kit "import-report.json")
Write-Host "copied $($copied.Count)"
$copied | Group-Object category | Sort-Object Name | ForEach-Object { Write-Host ("{0}`t{1}" -f $_.Count, $_.Name) }
