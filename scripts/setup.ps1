#requires -Version 7.0
param([string]$LocalCache='',[string]$PythonExecutable='',[switch]$SkipPython)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$deps=Join-Path $root '.deps'
$lock=Get-Content (Join-Path $root 'deps.lock.json') -Raw | ConvertFrom-Json
$repos=@(
    @{name='zephyr'; path='zephyr/zephyr'; cache='zephyr/zephyr'; revision=$lock.zephyr_commit; url='https://github.com/zephyrproject-rtos/zephyr.git'},
    @{name='cmsis'; path='zephyr/modules/hal/cmsis'; cache='zephyr/modules/hal/cmsis'; revision=$lock.cmsis_commit; url='https://github.com/zephyrproject-rtos/cmsis.git'},
    @{name='cmsis_6'; path='zephyr/modules/hal/cmsis_6'; cache='zephyr/modules/hal/cmsis_6'; revision=$lock.cmsis_6_commit; url='https://github.com/zephyrproject-rtos/cmsis_6.git'},
    @{name='hal_nxp'; path='zephyr/modules/hal/nxp'; cache='zephyr/modules/hal/nxp'; revision=$lock.hal_nxp_commit; url='https://github.com/zephyrproject-rtos/hal_nxp.git'},
    @{name='mcuboot'; path='zephyr/bootloader/mcuboot'; cache='zephyr/bootloader/mcuboot'; revision=$lock.mcuboot_commit; url='https://github.com/zephyrproject-rtos/mcuboot.git'},
    @{name='mbedtls'; path='zephyr/modules/crypto/mbedtls'; cache='zephyr/modules/crypto/mbedtls'; revision=$lock.mbedtls_commit; url='https://github.com/zephyrproject-rtos/mbedtls.git'},
    @{name='cannectivity'; path='cannectivity'; cache='cannectivity'; revision=$lock.cannectivity_commit; url='https://github.com/CANnectivity/cannectivity.git'}
)
foreach($repo in $repos) {
    $target=Join-Path $deps $repo.path
    if (-not (Test-Path (Join-Path $target '.git'))) {
        New-Item -ItemType Directory -Force (Split-Path $target -Parent) | Out-Null
        $cached=if($LocalCache){Join-Path $LocalCache $repo.cache}else{''}
        if ($cached -and (Test-Path (Join-Path $cached '.git'))) {
            & git clone --local $cached $target
        } else {
            New-Item -ItemType Directory -Force $target | Out-Null
            & git -C $target init
            if ($LASTEXITCODE) { throw "Git initialization failed: $($repo.name)" }
            & git -C $target fetch --depth 1 $repo.url $repo.revision
            if ($LASTEXITCODE) { throw "Fetch failed: $($repo.name)" }
            & git -C $target checkout --detach FETCH_HEAD
        }
        if ($LASTEXITCODE) { throw "Checkout failed: $($repo.name)" }
    }
    if ((& git -C $target rev-parse HEAD).Trim() -ne $repo.revision) {
        throw "Revision mismatch: $($repo.name)"
    }
    if ($repo.name -ne 'cannectivity') {
        & git -C $target diff --quiet HEAD --
        if ($LASTEXITCODE) { throw "Unexpected dependency edits: $($repo.name)" }
    }
}
$cannectivity=Join-Path $deps 'cannectivity'
$patch=Join-Path $root 'patches/cannectivity-elroot-port.patch'
$paths=@('app/src/usb.c','subsys/usb/device/class/gs_usb.c')
$actual=(& git -C $cannectivity diff -- @paths) -join "`n"
if (-not $actual) {
    & git -C $cannectivity apply $patch
    if ($LASTEXITCODE) { throw 'CANnectivity port patch failed.' }
    $actual=(& git -C $cannectivity diff -- @paths) -join "`n"
}
$expected=(Get-Content -LiteralPath $patch) -join "`n"
if ($actual -ne $expected) { throw 'CANnectivity port patch drift.' }
$changed=@(& git -C $cannectivity diff --name-only HEAD --)
if ($changed.Count -ne 2 -or $changed[0] -ne $paths[0] -or $changed[1] -ne $paths[1]) {
    throw 'Unexpected CANnectivity dependency edits.'
}
if (-not (Select-String -LiteralPath (Join-Path $cannectivity 'LICENSE') -Pattern 'Apache License' -Quiet)) {
    throw 'CANnectivity Apache-2.0 license missing.'
}
if (-not $SkipPython) {
    $python=Join-Path $deps 'python/Scripts/python.exe'
    if (-not (Test-Path $python)) {
        if (-not $PythonExecutable) { $PythonExecutable=(Get-Command python -ErrorAction Stop).Source }
        $sourceVersion=(& $PythonExecutable -c 'import sys; print("%d.%d" % sys.version_info[:2])').Trim()
        if ([version]$sourceVersion -lt [version]'3.12') { throw 'Python 3.12+ is required; pass -PythonExecutable.' }
        & $PythonExecutable -m venv (Join-Path $deps 'python')
        if ($LASTEXITCODE) { throw 'Python virtual environment creation failed.' }
    }
    $venvVersion=(& $python -c 'import sys; print("%d.%d" % sys.version_info[:2])').Trim()
    if ([version]$venvVersion -lt [version]'3.12') { throw 'Existing .deps/python uses Python below 3.12.' }
    & $python -m pip install -r (Join-Path $PSScriptRoot 'requirements.lock.txt')
    if ($LASTEXITCODE) { throw 'Pinned Python dependency installation failed.' }
}
Write-Host "Pinned CANnectivity $($lock.cannectivity_commit) and Zephyr modules ready."
