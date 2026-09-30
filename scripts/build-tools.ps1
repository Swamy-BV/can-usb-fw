function Get-FwBuildTools {
    $cmakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
    $ninjaCommand = Get-Command ninja -ErrorAction SilentlyContinue
    $cmakePath = if ($cmakeCommand) { $cmakeCommand.Source } else { $null }
    $ninjaPath = if ($ninjaCommand) { $ninjaCommand.Source } else { $null }
    if (-not $cmakePath -or -not $ninjaPath) {
        $vswherePath = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
        if (Test-Path -LiteralPath $vswherePath) {
            $vsInstall = & $vswherePath -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
            if ($vsInstall) {
                $vsCmakeRoot = Join-Path $vsInstall 'Common7/IDE/CommonExtensions/Microsoft/CMake'
                if (-not $cmakePath) { $cmakePath = Join-Path $vsCmakeRoot 'CMake/bin/cmake.exe' }
                if (-not $ninjaPath) { $ninjaPath = Join-Path $vsCmakeRoot 'Ninja/ninja.exe' }
            }
        }
    }
    if (-not $cmakePath -or -not (Test-Path -LiteralPath $cmakePath)) { throw 'Install CMake 3.30+ or Visual Studio C++ tools.' }
    if (-not $ninjaPath -or -not (Test-Path -LiteralPath $ninjaPath)) { throw 'Install Ninja 1.12+ or Visual Studio C++ tools.' }
    return @{cmake=$cmakePath; ninja=$ninjaPath}
}
