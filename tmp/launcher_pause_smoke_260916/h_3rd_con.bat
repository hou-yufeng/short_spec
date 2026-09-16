@echo off
setlocal
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "RT=%ROOT%\rt"
set "OUTPUT=%ROOT%\h_3rd_con.xlsx"
set PYTHONUTF8=1
echo HTML Third-Batch ShortSpec - Consumer Laptop
echo Source: %ROOT%
echo Output: %OUTPUT%
echo.
pushd "%RT%\scripts"
"%RT%\python-runtime\python.exe" html_third_batch_runner.py --config con --source-dir "%ROOT%" --glob "*.html" --output-xlsx "%OUTPUT%"
set CODE=%ERRORLEVEL%
popd
echo.
if "%CODE%"=="0" (
  echo Completed successfully.
  echo Output: %OUTPUT%
  del /q "%ROOT%\*.html"
  echo Source HTML files deleted after successful generation.
) else (
  echo Failed with exit code %CODE%.
)
echo.
if not "%NO_PAUSE%"=="1" pause
exit /b %CODE%
