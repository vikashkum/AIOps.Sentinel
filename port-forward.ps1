# AIOps Sentinel — Port Forwards for Docker Desktop Multi-Node Kubernetes
#
# Why this is needed:
#   Docker Desktop multi-node Kubernetes runs nodes as containers inside a
#   Docker network (172.20.0.x). Those IPs are not routable from Windows.
#   kubectl port-forward tunnels traffic from Windows localhost → kube API → pod.
#
# Usage:
#   .\port-forward.ps1          # start all forwards
#   .\port-forward.ps1 -Stop    # terminate all forward jobs

param([switch]$Stop)

$namespace = "aiops-sentinel"

$forwards = @(
    @{ Name="backend";    Local=8000;  Remote=8000;  Label="app.kubernetes.io/component=backend" },
    @{ Name="frontend";   Local=3000;  Remote=80;    Label="app.kubernetes.io/component=frontend" },
    @{ Name="prometheus"; Local=9090;  Remote=9090;  Label="app.kubernetes.io/component=prometheus" },
    @{ Name="grafana";    Local=3001;  Remote=3000;  Label="app.kubernetes.io/component=grafana" }
)

if ($Stop) {
    Write-Host "Stopping all port-forward jobs..." -ForegroundColor Yellow
    Get-Job -Name "pf-*" -ErrorAction SilentlyContinue | Stop-Job | Remove-Job
    Write-Host "All port-forward jobs stopped." -ForegroundColor Green
    exit 0
}

# Kill any existing forward jobs first
Get-Job -Name "pf-*" -ErrorAction SilentlyContinue | Stop-Job | Remove-Job

Write-Host ""
Write-Host "Starting AIOps Sentinel port-forwards..." -ForegroundColor Cyan
Write-Host ""

foreach ($fwd in $forwards) {
    $job = Start-Job -Name "pf-$($fwd.Name)" -ScriptBlock {
        param($ns, $local, $remote, $label)
        kubectl port-forward -n $ns "svc/aiops-$label" "${local}:${remote}" 2>&1
    } -ArgumentList $namespace, $fwd.Local, $fwd.Remote, $fwd.Name

    Write-Host "  [OK] $($fwd.Name.PadRight(12)) http://localhost:$($fwd.Local)" -ForegroundColor Green
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  Frontend:   http://localhost:3000" -ForegroundColor White
Write-Host "  Backend:    http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Prometheus: http://localhost:9090" -ForegroundColor White
Write-Host "  Grafana:    http://localhost:3001  (admin / admin)" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Press Ctrl+C to stop all forwards, or run: .\port-forward.ps1 -Stop" -ForegroundColor DarkGray
Write-Host ""

# Keep the script alive and show job output
try {
    while ($true) {
        Start-Sleep -Seconds 5
        $failed = Get-Job -Name "pf-*" | Where-Object { $_.State -eq "Failed" }
        foreach ($j in $failed) {
            Write-Host "  [WARN] $($j.Name) failed — restarting..." -ForegroundColor Yellow
            $j | Remove-Job
            # find which forward failed and restart it
            $name = $j.Name -replace "^pf-",""
            $fwd = $forwards | Where-Object { $_.Name -eq $name }
            if ($fwd) {
                Start-Job -Name "pf-$($fwd.Name)" -ScriptBlock {
                    param($ns, $local, $remote, $svcName)
                    kubectl port-forward -n $ns "svc/aiops-$svcName" "${local}:${remote}" 2>&1
                } -ArgumentList $namespace, $fwd.Local, $fwd.Remote, $fwd.Name | Out-Null
            }
        }
    }
} finally {
    Write-Host "`nStopping port-forwards..." -ForegroundColor Yellow
    Get-Job -Name "pf-*" -ErrorAction SilentlyContinue | Stop-Job | Remove-Job
}
