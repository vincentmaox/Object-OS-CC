$ErrorActionPreference = 'Stop'

$taskName = 'ProjectOSDailyReport'
$python = 'D:\miniconda3\python.exe'
$script = 'D:\ClaudeCodeProjects\_ProjectOS\agent\daily_projectos_report.py'
$workdir = 'D:\ClaudeCodeProjects\_ProjectOS\agent'

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $python -Argument "-u `"$script`"" -WorkingDirectory $workdir
$trigger = New-ScheduledTaskTrigger -Daily -At '09:07'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'ProjectOS scan + Feishu base sync + morning report + blocker alert' -Force | Format-List TaskName,State
