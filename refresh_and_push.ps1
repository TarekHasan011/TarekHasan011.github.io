# Daily refresh run by Windows Task Scheduler on this computer.
#
# Google Scholar blocks GitHub's servers, so the Scholar data is fetched here
# instead, then pushed. GitHub Pages republishes the site after each push.
#
# Run by hand:  powershell -ExecutionPolicy Bypass -File refresh_and_push.ps1
# Log:          refresh.log (in this folder; not committed)

$ErrorActionPreference = 'Continue'
$repo   = $PSScriptRoot
$python = 'C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe'
$git    = 'C:\Program Files\Git\cmd\git.exe'
$log    = Join-Path $repo 'refresh.log'

$env:GIT_TERMINAL_PROMPT = '0'   # never wait for a password prompt
$env:GCM_INTERACTIVE     = 'never'

function Log($msg) {
    $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $log -Value $line -Encoding utf8
}

# Keep the log short: last 300 lines
if (Test-Path $log) { Get-Content $log -Tail 300 | Set-Content $log -Encoding utf8 }

Set-Location $repo
Log '--- refresh started'

# 1. Get GitHub's latest commits first (the GitHub job also commits data daily)
& $git pull --rebase --autostash --quiet origin main 2>&1 | ForEach-Object { Log "git: $_" }

# 2. Fetch Google Scholar, journal metrics and new abstracts
& $python -B refresh_data.py 2>&1 | ForEach-Object { Log "$_" }

# 3. Commit and push only the data files, and only if they changed
& $git add site/data
& $git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Log 'No data changes; nothing to push.'
} else {
    & $git commit --quiet -m 'Daily data refresh (Google Scholar)' 2>&1 | ForEach-Object { Log "git: $_" }
    & $git push --quiet origin main 2>&1 | ForEach-Object { Log "git: $_" }
    if ($LASTEXITCODE -eq 0) { Log 'Pushed; GitHub Pages will republish the site.' } else { Log 'Push FAILED (see lines above).' }
}
Log '--- refresh finished'
