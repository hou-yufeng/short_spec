@echo off
setlocal
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "RT=%ROOT%\rt"
set "OUTPUT=%ROOT%\h_3rd_ts.xlsx"
set PYTHONUTF8=1
pushd "%RT%\scripts"
"%RT%\python-runtime\python.exe" html_third_batch_runner.py --config ts --source-dir "%ROOT%" --glob "*.html" --output-xlsx "%OUTPUT%"
set CODE=%ERRORLEVEL%
popd
if not "%CODE%"=="0" exit /b %CODE%
del /q "%ROOT%\*.html"
exit /b 0
