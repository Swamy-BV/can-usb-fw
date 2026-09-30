#requires -Version 7.0
param(
    [uint16]$VendorId=8137,
    [uint16]$ProductId=162,
    [string]$Version='1.1.9',
    [string]$ToolchainPath='',
    [string]$KeyPath=''
)
$ErrorActionPreference='Stop'
$root=(Split-Path $PSScriptRoot -Parent).Replace('\','/')
. "$PSScriptRoot/build-tools.ps1"
$tools=Get-FwBuildTools
if ($VendorId -ne 8137 -or $ProductId -ne 162) {
    throw 'Only the authorized lab USB identity 1FC9:00A2 is configured for this project.'
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Use a numeric application version.' }
if (-not $ToolchainPath) { $ToolchainPath=$env:GNUARMEMB_TOOLCHAIN_PATH }
if (-not $ToolchainPath) { throw 'Pass -ToolchainPath for Arm GNU 14.2.rel1.' }
$ToolchainPath=(Resolve-Path $ToolchainPath).Path.Replace('\','/')
if (-not (Test-Path "$ToolchainPath/bin/arm-none-eabi-gcc.exe")) { throw 'Arm GCC not found.' }
if (-not $KeyPath) { $KeyPath="$root/.deps/dfu-development.pem" }
$KeyPath=(Resolve-Path $KeyPath).Path.Replace('\','/')
if (-not (Test-Path $KeyPath)) { throw 'Installed MCUboot development signing key not found.' }
$python="$root/.deps/python/Scripts/python.exe"
if (-not (Test-Path $python)) { throw 'Run scripts/setup.ps1 first.' }
& "$PSScriptRoot/setup.ps1" -SkipPython
if ($LASTEXITCODE) { throw 'Pinned dependency setup failed.' }
$lock=Get-Content "$root/deps.lock.json" -Raw | ConvertFrom-Json
$workspace="$root/.deps/zephyr"
$modules=@(
    "$workspace/modules/hal/cmsis",
    "$workspace/modules/hal/cmsis_6",
    "$workspace/modules/hal/nxp",
    "$workspace/bootloader/mcuboot",
    "$workspace/modules/crypto/mbedtls",
    "$root/.deps/cannectivity",
    "$root/platform/usb_guard"
)
$target="$root/build/frdm_mcxn236"
$evidence="$root/evidence/build-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))"
New-Item -ItemType Directory -Force $target,$evidence | Out-Null
$identity="$root/build/identity.conf"
@(
    ('CONFIG_USB_DEVICE_VID=0x{0:X4}' -f $VendorId),
    ('CONFIG_USB_DEVICE_PID=0x{0:X4}' -f $ProductId),
    ('CONFIG_CANNECTIVITY_USB_VID=0x{0:X4}' -f $VendorId),
    ('CONFIG_CANNECTIVITY_USB_PID=0x{0:X4}' -f $ProductId),
    ('CONFIG_USB_DEVICE_DFU_PID=0x{0:X4}' -f $ProductId),
    ('CONFIG_MCUBOOT_SIGNATURE_KEY_FILE="'+$KeyPath+'"'),
    ('CONFIG_MCUBOOT_IMGTOOL_SIGN_VERSION="'+$Version+'"')
) | Set-Content $identity
$saved=@{}
foreach($name in @('PATH','ZEPHYR_BASE','ZEPHYR_TOOLCHAIN_VARIANT','GNUARMEMB_TOOLCHAIN_PATH')) {
    $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
try {
    $env:PATH="$root/.deps/python/Scripts;$(Split-Path $tools.ninja);$env:PATH"
    $env:ZEPHYR_BASE="$workspace/zephyr"
    $env:ZEPHYR_TOOLCHAIN_VARIANT='gnuarmemb'
    $env:GNUARMEMB_TOOLCHAIN_PATH=$ToolchainPath
    $conf="$root/board/frdm_mcxn236.conf;$root/board/mcuboot.conf;$identity"
    & $tools.cmake -S "$root/.deps/cannectivity/app" -B $target -G Ninja -DBOARD=frdm_mcxn236 "-DPython3_EXECUTABLE=$python" "-DZEPHYR_MODULES=$($modules -join ';')" "-DEXTRA_CONF_FILE=$conf" "-DEXTRA_DTC_OVERLAY_FILE=$root/board/partitions.overlay" 2>&1 | Tee-Object "$evidence/configure.log"
    if ($LASTEXITCODE) { throw 'MCX configure failed.' }
    & $tools.cmake --build $target 2>&1 | Tee-Object "$evidence/build.log"
    if ($LASTEXITCODE) { throw 'MCX build failed.' }
    $signed="$target/zephyr/zephyr.signed.bin"
    $package="$target/zephyr/can-usb.dfu"
    & $python "$PSScriptRoot/package-dfu.py" $signed $KeyPath "$workspace/bootloader/mcuboot/scripts" $package --vid $VendorId --pid $ProductId 2>&1 | Tee-Object "$evidence/package.json"
    if ($LASTEXITCODE) { throw 'Signed image or DFU package check failed.' }
    $sources=@{}
    foreach($folder in @('board','patches','platform','scripts')) {
        Get-ChildItem "$root/$folder" -Recurse -File |
            Where-Object { $_.FullName -notmatch '[/\\]__pycache__[/\\]' -and $_.Extension -ne '.pyc' } |
            ForEach-Object {
            $sources[$_.FullName.Replace('\','/').Substring($root.Length+1)]=(Get-FileHash $_.FullName).Hash.ToLowerInvariant()
        }
    }
    $result=@{
        status='build-passed'; profile='cannectivity-frdm-mcxn236'; version=$Version
        upstream_commit=$lock.cannectivity_commit; zephyr_commit=$lock.zephyr_commit
        vid=$VendorId; pid=$ProductId; actual_channels=1
        signed_sha256=(Get-FileHash $signed).Hash.ToLowerInvariant()
        dfu_sha256=(Get-FileHash $package).Hash.ToLowerInvariant()
        usb_enumeration_tested=$false; physical_can_qualified=$false; sources=$sources
    }
    $result | ConvertTo-Json -Depth 5 | Set-Content "$evidence/result.json"
    Write-Host "Signed DFU package: $package"
    Write-Host "Build evidence: $evidence"
} catch {
    @{status='failed';error=$_.Exception.Message} | ConvertTo-Json | Set-Content "$evidence/result.json"
    throw
} finally {
    foreach($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
}
