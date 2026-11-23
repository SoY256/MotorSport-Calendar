# Build the signed release bundle and publish it to the Google Play closed
# testing track (Alpha, 100%, sent for review) without a browser login.
#
#   powershell -File scripts/release_android.ps1 -Notes "What changed"
#
# Uses the version in pubspec.yaml, the upload keystore described by
# key.properties in $env:SECAR_SIGNING_DIR and the Play service-account key
# (see scripts/publish_play.py). Nothing secret is written to the repository.
param(
    [Parameter(Mandatory = $true)][string]$Notes,
    [string]$Track = "alpha",
    [switch]$NoCommit
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-ReleaseSetting([string]$Name, [string]$DefaultValue) {
    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not $value) { $value = [Environment]::GetEnvironmentVariable($Name, "User") }
    if ($value) { return $value }
    return $DefaultValue
}
$signing = Get-ReleaseSetting "SECAR_SIGNING_DIR" (Join-Path $env:USERPROFILE ".secar\signing")
$flutter = Get-ReleaseSetting "SECAR_FLUTTER" "C:\Users\soy25\Documents\ChatGPT\Motorsport-Calendar\.tools\flutter\bin\flutter.bat"
$env:PUB_CACHE = Get-ReleaseSetting "PUB_CACHE" (Join-Path $env:LOCALAPPDATA "Pub\Cache")
$env:GRADLE_USER_HOME = Get-ReleaseSetting "GRADLE_USER_HOME" (Join-Path $env:USERPROFILE ".gradle")
$env:PUB_CACHE = python -c "from pathlib import Path;import sys;print(Path(sys.argv[1]).resolve())" $env:PUB_CACHE
if ($LASTEXITCODE -ne 0) { throw "Could not resolve the Pub cache location" }
$expectedCertificate = "819a023ad96c5158"

$version = (Select-String -Path pubspec.yaml -Pattern '^version:\s*(\S+)\+(\d+)').Matches[0]
$name = $version.Groups[1].Value
$code = $version.Groups[2].Value
$bundle = Join-Path $root "release\secar-$name-$code.aab"

$properties = Get-Content (Join-Path $signing "key.properties") -Raw
$store = (($properties -split "`n" | Where-Object { $_ -match '^storeFile=' }) -replace '^storeFile=', '').Trim()
if (-not [IO.Path]::IsPathRooted($store)) { $store = (Resolve-Path (Join-Path "$signing\app" $store)).Path }
$temporarySigning = Join-Path $root "android\key.properties"
if (Test-Path -LiteralPath $temporarySigning) { throw "Refusing to overwrite an existing android\key.properties" }
try {
    [IO.File]::WriteAllText($temporarySigning, ($properties -replace '(?m)^storeFile=.*$', ('storeFile=' + $store.Replace('\', '/'))))
    $env:FLUTTER_SUPPRESS_ANALYTICS = "true"
    # Isolate release builds from compiler daemons/caches shared across worktrees and drive aliases.
    & $flutter build appbundle --release --no-android-gradle-daemon --android-project-arg=kotlin.incremental=false --android-project-arg=kotlin.compiler.execution.strategy=in-process
    if ($LASTEXITCODE -ne 0) { throw "flutter build appbundle failed" }
}
finally {
    if (Test-Path -LiteralPath $temporarySigning) { Remove-Item -LiteralPath $temporarySigning -ErrorAction Stop }
}
New-Item -ItemType Directory -Force (Split-Path $bundle) | Out-Null
Copy-Item build\app\outputs\bundle\release\app-release.aab $bundle -Force

$certificate = python -c "import sys,zipfile,hashlib;from cryptography.hazmat.primitives.serialization import pkcs7,Encoding;c=pkcs7.load_der_pkcs7_certificates(zipfile.ZipFile(sys.argv[1]).read('META-INF/UPLOAD.RSA'))[0];print(hashlib.sha256(c.public_bytes(Encoding.DER)).hexdigest()[:16])" $bundle
if ($certificate -ne $expectedCertificate) { throw "Bundle is not signed with the Secar upload key ($certificate)" }

$arguments = @("scripts/publish_play.py", "--aab", $bundle, "--notes", $Notes, "--track", $Track)
if ($NoCommit) { $arguments += "--no-commit" }
python @arguments
if ($LASTEXITCODE -ne 0) { throw "Publishing failed" }
