#requires -Version 7.0
param([string]$ToolchainPath='',[string]$KeyPath='')
$ErrorActionPreference='Stop'
$root=(Split-Path $PSScriptRoot -Parent).Replace('\','/')
. "$PSScriptRoot/build-tools.ps1"
$tools=Get-FwBuildTools
if (-not $ToolchainPath) { $ToolchainPath=$env:GNUARMEMB_TOOLCHAIN_PATH }
if (-not $ToolchainPath) { throw 'Pass -ToolchainPath for Arm GNU 14.2.rel1.' }
$ToolchainPath=(Resolve-Path $ToolchainPath).Path.Replace('\','/')
if (-not (Test-Path "$ToolchainPath/bin/arm-none-eabi-gcc.exe")) { throw 'Arm GCC not found.' }
if (-not $KeyPath) { $KeyPath="$root/.deps/dfu-development.pem" }
$KeyPath=(Resolve-Path $KeyPath).Path.Replace('\','/')
$python="$root/.deps/python/Scripts/python.exe"
if (-not (Test-Path $python)) { throw 'Run scripts/setup.ps1 first.' }
& "$PSScriptRoot/setup.ps1" -SkipPython
if ($LASTEXITCODE) { throw 'Pinned dependency setup failed.' }
$workspace="$root/.deps/zephyr"
$modules=@(
    "$workspace/modules/hal/cmsis",
    "$workspace/modules/hal/cmsis_6",
    "$workspace/modules/hal/nxp",
    "$workspace/bootloader/mcuboot",
    "$workspace/modules/crypto/mbedtls",
    "$root/platform/usb_guard"
)
$target="$root/build/mcuboot-frdm_mcxn236"
$evidence="$root/evidence/bootloader-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))"
New-Item -ItemType Directory -Force $target,$evidence | Out-Null
$identity="$root/build/bootloader-identity.conf"
@(
    'CONFIG_USB_DEVICE_VID=0x1FC9',
    'CONFIG_USB_DEVICE_PID=0x00A2',
    'CONFIG_USB_DEVICE_DFU_PID=0x00A2',
    ('CONFIG_BOOT_SIGNATURE_KEY_FILE="'+$KeyPath+'"')
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
    $conf="$root/board/mcuboot-bootloader.conf;$identity"
    & $tools.cmake -S "$workspace/bootloader/mcuboot/boot/zephyr" -B $target -G Ninja '-UCONFIG_BOOT_SIGNATURE_KEY_FILE' -DBOARD=frdm_mcxn236 "-DPython3_EXECUTABLE=$python" "-DZEPHYR_MODULES=$($modules -join ';')" "-DEXTRA_CONF_FILE=$conf" "-DEXTRA_DTC_OVERLAY_FILE=$root/board/partitions.overlay" 2>&1 | Tee-Object "$evidence/configure.log"
    if ($LASTEXITCODE) { throw 'MCUboot configure failed.' }
    & $tools.cmake --build $target 2>&1 | Tee-Object "$evidence/build.log"
    if ($LASTEXITCODE) { throw 'MCUboot build failed.' }
    $binary="$target/zephyr/zephyr.bin"
    $result=@{
        status='build-passed'; board='frdm_mcxn236'; vid='1FC9'; pid='00A2'
        bootloader_sha256=(Get-FileHash $binary).Hash.ToLowerInvariant()
        bootloader_commit=(Get-Content "$root/deps.lock.json" -Raw | ConvertFrom-Json).mcuboot_commit
        flashed_to_board=$false; bootloader_self_update_tested=$false
    }
    $result | ConvertTo-Json -Depth 4 | Set-Content "$evidence/result.json"
    Write-Host "MCUboot binary: $binary"
    Write-Host "Build evidence: $evidence"
} catch {
    @{status='failed';error=$_.Exception.Message} | ConvertTo-Json | Set-Content "$evidence/result.json"
    throw
} finally {
    foreach($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
}
