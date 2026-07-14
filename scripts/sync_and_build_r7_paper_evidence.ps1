param(
    [string]$SshHost = "zijian@172.18.0.40",
    [Parameter(Mandatory = $true)][string]$RemoteQueueRoot,
    [Parameter(Mandatory = $true)][string]$ExpectedManifestSha256,
    [string]$OutputBase = "docs/reports/data"
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$AttemptRoot = Join-Path $OutputBase "$stamp-r7-readonly-sync"
if (Test-Path -LiteralPath $AttemptRoot) {
    throw "dated attempt already exists: $AttemptRoot"
}
New-Item -ItemType Directory -Path $AttemptRoot | Out-Null
$snapshot = Join-Path $AttemptRoot "snapshot"
New-Item -ItemType Directory -Path (Join-Path $snapshot "queue") -Force | Out-Null

function Copy-RemoteFile([string]$RelativePath) {
    $target = Join-Path $snapshot $RelativePath
    $parent = Split-Path -Parent $target
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $remote = "${SshHost}:$RemoteQueueRoot/$RelativePath"
    & scp -q -- $remote $target
    if ($LASTEXITCODE -ne 0) { throw "read-only scp failed: $RelativePath" }
}

Copy-RemoteFile "queue/queue_seed100.json"
$manifestPath = Join-Path $snapshot "queue/queue_seed100.json"
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLower()
if ($actual -ne $ExpectedManifestSha256.ToLower()) {
    throw "manifest SHA-256 mismatch: expected=$ExpectedManifestSha256 actual=$actual"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$active = @($manifest.tasks | Where-Object { $_.branch -eq "e1_pass" })
if ($manifest.tasks.Count -ne 22 -or $active.Count -ne 14) {
    throw "frozen r7 matrix mismatch"
}

foreach ($task in $active) {
    $bytes = [Text.Encoding]::UTF8.GetBytes([string]$task.task_id)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $recordName = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLower() + ".json" }
    finally { $sha.Dispose() }
    $recordRelative = "state/tasks/$recordName"
    & ssh $SshHost "test -f '$RemoteQueueRoot/$recordRelative'"
    if ($LASTEXITCODE -eq 0) { Copy-RemoteFile $recordRelative }
}

& ssh $SshHost "test -f '$RemoteQueueRoot/markers/RISK-08_EXIT.json' -a -f '$RemoteQueueRoot/state/TERMINAL.json'"
$terminal = $LASTEXITCODE -eq 0
if ($terminal) {
    Copy-RemoteFile "markers/RISK-08_EXIT.json"
    Copy-RemoteFile "state/TERMINAL.json"
    foreach ($task in $active) {
        Copy-RemoteFile "logs/tasks/$($task.task_id).log"
        foreach ($relative in $task.success_artifacts) { Copy-RemoteFile ([string]$relative) }
        $runRelative = ([string]$task.success_artifacts[1]) -replace "/artifact_manifest.json$", "/single_train.log"
        Copy-RemoteFile $runRelative
    }
}

$evidenceDir = Join-Path $AttemptRoot "paper-evidence"
$builderArgs = @(
    "scripts/build_r7_paper_evidence.py",
    "--queue-root", $snapshot,
    "--source-queue-root", $RemoteQueueRoot,
    "--expected-manifest-sha256", $ExpectedManifestSha256,
    "--output-dir", $evidenceDir
)
if (-not $terminal) { $builderArgs += "--allow-not-ready" }
& python @builderArgs
if ($LASTEXITCODE -ne 0) { throw "fail-closed paper evidence builder rejected the snapshot" }

$statusPath = Join-Path $evidenceDir "paper_evidence_status.json"
if (-not (Test-Path -LiteralPath $statusPath)) { throw "paper_evidence_status.json was not emitted" }
Write-Output $AttemptRoot
