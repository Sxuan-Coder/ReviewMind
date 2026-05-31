# ============================================================
# ReviewMind Docker 一键启动脚本 (Windows PowerShell)
# 使用方法: 右键 setup.ps1 → "使用 PowerShell 运行"
#          或在终端执行: .\setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ReviewMind Docker 一键部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 Docker Desktop
Write-Host "[1/4] 检查 Docker 环境..." -ForegroundColor Yellow
$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Docker Desktop 未运行，请先启动 Docker Desktop" -ForegroundColor Red
    Write-Host "  下载地址: https://www.docker.com/products/docker-desktop/" -ForegroundColor Gray
    pause
    exit 1
}
Write-Host "  [OK] Docker 运行正常" -ForegroundColor Green

# 2. 检查 .env 文件
Write-Host "[2/4] 检查环境配置..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "  [INFO] .env 不存在，从模板创建..." -ForegroundColor Gray
    if (Test-Path "backend\.env.example") {
        Copy-Item "backend\.env.example" ".env"
        # 确保 mock 模式开启（无需 API Key 也能跑）
        (Get-Content ".env") -replace 'LLM_MOCK_MODE=.*', 'LLM_MOCK_MODE=true' | Set-Content ".env"
        (Get-Content ".env") -replace 'DATABASE_URL=.*', 'DATABASE_URL=postgresql+asyncpg://reviewmind:reviewmind@postgres:5432/reviewmind' | Set-Content ".env"
        (Get-Content ".env") -replace 'REDIS_URL=.*', 'REDIS_URL=redis://redis:6379/0' | Set-Content ".env"
        Write-Host "  [OK] .env 已创建（Mock 模式）" -ForegroundColor Green
        Write-Host "  [INFO] 如需真实 AI 审查，请编辑 .env 填入 API Key 并设 LLM_MOCK_MODE=false" -ForegroundColor Gray
    }
} else {
    Write-Host "  [OK] .env 已存在" -ForegroundColor Green
}

# 3. 拉取镜像并启动
Write-Host "[3/4] 构建并启动容器..." -ForegroundColor Yellow
Write-Host "  (首次构建需下载镜像，可能需要几分钟)" -ForegroundColor Gray
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] 容器启动失败，请检查上方日志" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "  [OK] 容器已启动" -ForegroundColor Green

# 4. 等待服务就绪
Write-Host "[4/4] 等待服务就绪..." -ForegroundColor Yellow
$maxWait = 120
$elapsed = 0
do {
    Start-Sleep -Seconds 3
    $elapsed += 3
    try {
        $health = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($health.StatusCode -eq 200) {
            Write-Host "  [OK] 后端服务就绪" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "  ... 等待中 (${elapsed}s/${maxWait}s)" -ForegroundColor Gray
    }
} while ($elapsed -lt $maxWait)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   部署完成！" -ForegroundColor Green
Write-Host ""
Write-Host "   前端: http://localhost" -ForegroundColor White
Write-Host "   后端: http://localhost:8000" -ForegroundColor White
Write-Host "   API文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "   停止命令: docker compose down" -ForegroundColor Gray
Write-Host "   查看日志: docker compose logs -f" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 自动打开浏览器
Start-Process "http://localhost"
pause
