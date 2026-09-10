# v0.7.0 信息减负（2026-09-10）：日报任务改造
# - ProjectOSDailyReport        : 09:07 -> 09:00（早报按老茅要求 9 点整）
# - ProjectOS_DailyRecap_Evening: 22:57 daily_recap.py -> 21:30 daily_digest.py --evening

$ErrorActionPreference = 'Stop'

# --- 早任务：只改时间 ---
$m = Get-ScheduledTask -TaskName 'ProjectOSDailyReport'
$m.Triggers[0].StartBoundary = '2026-09-11T09:00:00'
Set-ScheduledTask -InputObject $m | Out-Null
Write-Host "morning -> 09:00 OK"

# --- 晚任务：改时间 + 改执行脚本 ---
$e = Get-ScheduledTask -TaskName 'ProjectOS_DailyRecap_Evening'
$e.Triggers[0].StartBoundary = '2026-09-10T21:30:00'
$e.Actions[0].Execute   = 'D:\miniconda3\python.exe'
$e.Actions[0].Arguments = '-u "D:\ClaudeCodeProjects\_ProjectOS\agent\daily_digest.py" --evening'
Set-ScheduledTask -InputObject $e | Out-Null
Write-Host "evening -> 21:30 daily_digest.py OK"

# --- 验证 ---
Get-ScheduledTask -TaskName 'ProjectOSDailyReport','ProjectOS_DailyRecap_Evening' |
    ForEach-Object {
        $info = $_ | Get-ScheduledTaskInfo
        "{0}: {1} {2} | next={3}" -f $_.TaskName, $_.Actions[0].Execute, $_.Actions[0].Arguments, $info.NextRunTime
    }
