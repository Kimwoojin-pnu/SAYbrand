$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python).Source

$tasks = @(
    @{
        Name    = "CardNews-Generate"
        Script  = "run.py"
        Hour    = 12
        Minute  = 30
        Comment = "Generate card news and send to Discord"
    },
    @{
        Name    = "CardNews-CheckReview"
        Script  = "check_review.py"
        Hour    = 14
        Minute  = 0
        Comment = "Check Discord review and upload to YouTube"
    },
    @{
        Name    = "CardNews-HealthCheck"
        Script  = "health_check.py"
        Hour    = 23
        Minute  = 0
        Comment = "Check upload status and send alert if missing"
    }
)

foreach ($task in $tasks) {
    $scriptPath = Join-Path $ProjectRoot $task.Script
    $action = New-ScheduledTaskAction `
        -Execute $Python `
        -Argument $scriptPath `
        -WorkingDirectory $ProjectRoot

    $trigger = New-ScheduledTaskTrigger `
        -Daily `
        -At "$($task.Hour):$($task.Minute.ToString('D2'))"

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -RestartCount 1 `
        -RestartInterval (New-TimeSpan -Minutes 5) `
        -WakeToRun

    Register-ScheduledTask `
        -TaskName $task.Name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description $task.Comment `
        -Force | Out-Null

    Write-Host "Registered: $($task.Name) - Daily at $($task.Hour):$($task.Minute.ToString('D2'))"
}

Write-Host ""
Write-Host "Done. Verify with: Get-ScheduledTask -TaskName 'CardNews-*'"
