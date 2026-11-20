@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [druck-macro] 최신 데이터를 확인하고 리포트를 만드는 중입니다...
python -m druck run --open
if errorlevel 1 (
  echo.
  echo 실행 중 오류가 났습니다. 위 메시지를 확인하세요. 필요한 패키지: pip install -r requirements.txt
)
pause