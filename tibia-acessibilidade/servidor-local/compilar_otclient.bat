@echo off
rem Compila o OTClient (com o patch de acessibilidade) em local\otclient\build\windows-release.
rem Usa o Visual Studio 2022 (toolset v143) e o vcpkg clonado em local\vcpkg.
setlocal
set ROOT=%~dp0..\..
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" || exit /b 1
rem o vcvars64 aponta VCPKG_ROOT para o vcpkg do Visual Studio; usamos o clonado em local\vcpkg
set VCPKG_ROOT=%ROOT%\local\vcpkg
cd /d "%ROOT%\local\otclient" || exit /b 1
cmake --preset windows-release -DVCPKG_PLATFORM_TOOLSET=v143 -DOPTIONS_ENABLE_SCCACHE=OFF || exit /b 1
cmake --build --preset windows-release || exit /b 1
echo COMPILACAO_OK
