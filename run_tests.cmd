@echo off
REM BAYSIM birlesik test calistiricisi (Windows).
REM Godot yurutulebiliri: %BAYSIM_GODOT%, yoksa PATH uzerindeki "godot".
setlocal enabledelayedexpansion
cd /d "%~dp0"

if "%BAYSIM_GODOT%"=="" (set "GODOT=godot") else (set "GODOT=%BAYSIM_GODOT%")
set "FAILED=0"
set "GODOT_MISSING=0"

"%GODOT%" --version >nul 2>&1
if errorlevel 1 (
	echo !! Godot bulunamadi ^(%GODOT%^). BAYSIM_GODOT ayarlayin veya PATH'e ekleyin.
	echo !! GDScript testleri atlandi ^(dogrulanmadi^).
	set "GODOT_MISSING=1"
) else (
	for %%T in (test_geo_reference test_fdm_link test_airport_pack test_terrain_tile) do (
		echo == %%T ==
		set "OK=0"
		for /f "delims=" %%L in ('"%GODOT%" --headless --path . --script "res://tests/%%T.gd" 2^>^&1') do (
			echo %%L
			echo %%L | findstr /c:"%%T: OK" >nul && set "OK=1"
		)
		if "!OK!"=="1" (echo -- %%T: PASS) else (echo -- %%T: FAIL & set "FAILED=1")
		echo.
	)
)

echo == python unittest ^(launcher + world_builder^) ==
python -m unittest discover -s . -t . -v
if errorlevel 1 (echo -- python: FAIL & set "FAILED=1") else (echo -- python: PASS)

echo.
if not "%FAILED%"=="0" (echo BAZI TESTLER BASARISIZ & exit /b 1)
if not "%GODOT_MISSING%"=="0" (echo PYTHON TESTLERI GECTI - GDScript testleri Godot yoklugunda atlandi & exit /b 2)
echo TUM TESTLER GECTI
exit /b 0
