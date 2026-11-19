# Builds hdr10_patchgen.exe with the Visual Studio Build Tools (x64).
$vs = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat'
Set-Location $PSScriptRoot
cmd /c "`"$vs`" >nul && cl /nologo /O2 /EHsc /std:c++17 /W3 hdr10_patchgen.cpp /Fe:hdr10_patchgen.exe /link /SUBSYSTEM:CONSOLE"
