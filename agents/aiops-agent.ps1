<#
.SYNOPSIS
    AIOps Sentinel Windows Agent — collects IIS and Windows VM metrics
    and ships them to the AIOps Sentinel backend.

.DESCRIPTION
    Runs without admin rights. Collects:
      - CPU, memory, disk usage via WMI/CIM
      - IIS request/error metrics via IIS logs (read-only access)
      - Windows Event Log errors and warnings
      - IIS app pool status via WMI

    Usage:
      .\aiops-agent.ps1 -BackendUrl "http://<sentinel-host>:8000" -IntervalSeconds 30

    Run once (useful for testing):
      .\aiops-agent.ps1 -BackendUrl "http://localhost:8000" -RunOnce

    Schedule via Task Scheduler (no admin needed for creating user tasks):
      $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
                   -Argument "-NonInteractive -File C:\aiops-agent.ps1 -BackendUrl http://sentinel:8000"
      $trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Seconds 30) -Once -At (Get-Date)
      Register-ScheduledTask -TaskName "AIOps-Agent" -Action $action -Trigger $trigger -RunLevel Limited

.NOTES
    Requires: PowerShell 5.1+, read access to IIS log directory, no admin rights needed.
#>

param(
    [string]$BackendUrl     = "http://localhost:8000",
    [int]   $IntervalSeconds = 30,
    [switch]$RunOnce,
    [string]$HostOverride   = "",          # override auto-detected hostname
    [string]$IISLogPath     = "C:\inetpub\logs\LogFiles",
    [int]   $IISLogLines    = 200          # last N lines to scan per log file
)

$ErrorActionPreference = "SilentlyContinue"
$HostName = if ($HostOverride) { $HostOverride } else { $env:COMPUTERNAME.ToLower() }

# ── Helpers ───────────────────────────────────────────────────────────────────

function Send-Json {
    param([string]$Url, [object]$Body)
    try {
        $json = $Body | ConvertTo-Json -Depth 10 -Compress
        Invoke-RestMethod -Uri $Url -Method POST `
            -ContentType "application/json" `
            -Body $json `
            -TimeoutSec 8 | Out-Null
        return $true
    } catch {
        Write-Warning "[AIOps Agent] POST to $Url failed: $_"
        return $false
    }
}

function Get-Timestamp {
    return (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

# ── Windows VM Metrics ────────────────────────────────────────────────────────

function Collect-WindowsMetrics {
    # CPU
    $cpu = (Get-CimInstance -ClassName Win32_Processor |
            Measure-Object -Property LoadPercentage -Average).Average
    if ($null -eq $cpu) { $cpu = 0.0 }

    # Memory
    $os  = Get-CimInstance -ClassName Win32_OperatingSystem
    $memTotal = if ($os) { $os.TotalVisibleMemorySize } else { 1 }
    $memFree  = if ($os) { $os.FreePhysicalMemory     } else { 1 }
    $memPct   = [math]::Round((($memTotal - $memFree) / $memTotal) * 100, 1)

    # Disk (C: drive)
    $disk     = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='C:'"
    $diskPct  = if ($disk -and $disk.Size -gt 0) {
        [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100, 1)
    } else { 0.0 }

    # Network (first active adapter)
    $net      = Get-CimInstance -ClassName Win32_PerfFormattedData_Tcpip_NetworkInterface |
                Where-Object { $_.BytesTotalPersec -gt 0 } | Select-Object -First 1
    $bytesSent = if ($net) { [math]::Round($net.BytesSentPersec / 1MB, 3) } else { 0.0 }
    $bytesRecv = if ($net) { [math]::Round($net.BytesReceivedPersec / 1MB, 3) } else { 0.0 }

    return @{
        host             = $HostName
        host_type        = "windows"
        environment      = "production"
        timestamp        = Get-Timestamp
        cpu_pct          = [math]::Round([double]$cpu, 1)
        memory_pct       = $memPct
        disk_pct         = $diskPct
        bytes_sent_mb    = $bytesSent
        bytes_recv_mb    = $bytesRecv
        requests_per_sec = 0.0
        active_connections = 0
        error_rate_5xx_pct = 0.0
        latency_p99_ms   = 0.0
        app_pool_status  = "n/a"
        worker_process_count = 0
    }
}

# ── IIS Metrics ───────────────────────────────────────────────────────────────

function Collect-IISMetrics {
    param([ref]$BasePayload)

    # App pool status via WMI (no admin needed in most environments)
    try {
        $pools = Get-CimInstance -Namespace "root/WebAdministration" `
                     -ClassName ApplicationPool 2>$null
        $runningPools = ($pools | Where-Object { $_.ManagedPipelineMode -ne $null }).Count
        $BasePayload.Value.app_pool_status   = if ($runningPools -gt 0) { "running" } else { "unknown" }
        $BasePayload.Value.worker_process_count = $runningPools
    } catch {}

    # IIS Performance counters
    try {
        $iisReq = Get-CimInstance -ClassName Win32_PerfFormattedData_W3SVC_WebService `
                      -Filter "Name='_Total'" 2>$null
        if ($iisReq) {
            $BasePayload.Value.requests_per_sec    = [math]::Round($iisReq.TotalMethodRequestsPersec, 1)
            $BasePayload.Value.active_connections  = [int]$iisReq.CurrentConnections
            $total    = [double]($iisReq.TotalRequestsMethodPerSec + 1)
            $errors5  = [double]$iisReq.TotalHTTPRequestsRejected
            $BasePayload.Value.error_rate_5xx_pct  = [math]::Round(($errors5 / $total) * 100, 3)
        }
    } catch {}
}

# ── IIS Log Parsing ───────────────────────────────────────────────────────────

function Collect-IISLogs {
    if (-not (Test-Path $IISLogPath)) { return }

    $logFiles = Get-ChildItem -Path $IISLogPath -Recurse -Filter "*.log" |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 3   # last 3 active log files

    $allEntries = @()
    $fields = @("date","time","s-ip","cs-method","cs-uri-stem","cs-uri-query",
                "s-port","cs-username","c-ip","cs(User-Agent)","sc-status",
                "sc-substatus","sc-win32-status","time-taken")

    foreach ($file in $logFiles) {
        try {
            $lines = Get-Content -Path $file.FullName -Tail $IISLogLines -ErrorAction Stop
            foreach ($line in $lines) {
                if ($line -match "^#Fields:") {
                    $fields = ($line -replace "^#Fields:\s*","").Split(" ")
                    continue
                }
                if ($line.StartsWith("#") -or [string]::IsNullOrWhiteSpace($line)) { continue }

                $parts = $line.Split(" ")
                $rec   = @{}
                for ($i = 0; $i -lt $fields.Count -and $i -lt $parts.Count; $i++) {
                    $rec[$fields[$i]] = $parts[$i]
                }

                $status = 0
                [int]::TryParse($rec["sc-status"], [ref]$status) | Out-Null
                $timeTaken = 0
                [int]::TryParse($rec["time-taken"], [ref]$timeTaken) | Out-Null

                $allEntries += @{
                    host          = $HostName
                    method        = $rec["cs-method"]
                    uri           = $rec["cs-uri-stem"]
                    status_code   = $status
                    time_taken_ms = $timeTaken
                    client_ip     = $rec["c-ip"]
                    timestamp     = Get-Timestamp
                }
            }
        } catch {
            Write-Warning "[AIOps Agent] Could not read $($file.FullName): $_"
        }
    }

    if ($allEntries.Count -gt 0) {
        Send-Json -Url "$BackendUrl/ingest/iis/batch" -Body @{
            host    = $HostName
            entries = $allEntries
        } | Out-Null
    }
}

# ── Windows Event Log ─────────────────────────────────────────────────────────

function Collect-WinEvents {
    $cutoff = (Get-Date).AddSeconds(-$IntervalSeconds * 2)

    $logs = @("Application", "System")
    foreach ($logName in $logs) {
        try {
            $evts = Get-WinEvent -FilterHashtable @{
                LogName   = $logName
                Level     = @(1, 2, 3)   # Critical, Error, Warning
                StartTime = $cutoff
            } -MaxEvents 10 -ErrorAction Stop

            foreach ($evt in $evts) {
                $level = switch ($evt.Level) {
                    1 { "Critical" }
                    2 { "Error" }
                    3 { "Warning" }
                    default { "Information" }
                }

                Send-Json -Url "$BackendUrl/ingest/winevent" -Body @{
                    host      = $HostName
                    level     = $level
                    source    = $evt.ProviderName
                    event_id  = [int]$evt.Id
                    message   = $evt.Message -replace "`r`n"," " -replace "`n"," "
                    timestamp = $evt.TimeCreated.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
                }
            }
        } catch {}
    }
}

# ── Main Loop ─────────────────────────────────────────────────────────────────

function Run-Collection {
    Write-Host "[$(Get-Timestamp)] Collecting metrics for host: $HostName"

    # Collect base Windows metrics
    $payload = Collect-WindowsMetrics

    # Enrich with IIS metrics if IIS is present
    $iisPresent = Get-Service -Name "W3SVC" -ErrorAction SilentlyContinue
    if ($iisPresent) {
        Collect-IISMetrics -BasePayload ([ref]$payload)
        $payload.host_type = "iis"
        Collect-IISLogs
        Write-Host "  IIS detected — collecting app pool metrics and logs"
    }

    # Ship Windows VM metrics
    $ok = Send-Json -Url "$BackendUrl/ingest/windows" -Body $payload
    Write-Host "  Metrics shipped: $ok"

    # Ship Windows Event Log entries
    Collect-WinEvents
    Write-Host "  Event log entries shipped"
}

# ── Entry point ───────────────────────────────────────────────────────────────

Write-Host "======================================================"
Write-Host "  AIOps Sentinel Windows Agent"
Write-Host "  Host     : $HostName"
Write-Host "  Backend  : $BackendUrl"
Write-Host "  Interval : $IntervalSeconds seconds"
Write-Host "  IIS Logs : $IISLogPath"
Write-Host "======================================================"

if ($RunOnce) {
    Run-Collection
    Write-Host "RunOnce complete."
} else {
    Write-Host "Starting continuous collection. Press Ctrl+C to stop."
    while ($true) {
        Run-Collection
        Start-Sleep -Seconds $IntervalSeconds
    }
}
