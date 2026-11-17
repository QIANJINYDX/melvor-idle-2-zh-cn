param(
    [string]$GamePath = 'D:\Steam\steamapps\common\Melvor Idle 2'
)
$ErrorActionPreference = 'Stop'
$dll = Join-Path $GamePath 'data_GamesByMalcs.Melvor2_windows_x86_64\SmartFormat.dll'
[void][Reflection.Assembly]::LoadFrom($dll)
$checks = 0
foreach ($value in @(-0.15, 0.0, 0.15)) {
    $arguments = [Collections.Generic.Dictionary[string,object]]::new()
    $arguments.Add('Value', $value)
    $original = [SmartFormat.Smart]::Format('{Value:cond:<0?Decreased|>=0?Increased} {Value:0%}', [object]$arguments)
    $translated = [SmartFormat.Smart]::Format('{Value:cond:<0?降低|>=0?提高} {Value:0%}', [object]$arguments)
    $expected = $original.Replace('Decreased', '降低').Replace('Increased', '提高')
    if ($translated -ne $expected) { throw "Conditional branch mismatch for $value" }
    $checks++
}
$cases = @(
    @{ Items = [string[]]@(); Expected = '' },
    @{ Items = [string[]]@('甲'); Expected = '甲' },
    @{ Items = [string[]]@('甲','乙'); Expected = '甲和乙' },
    @{ Items = [string[]]@('甲','乙','丙'); Expected = '甲、乙和丙' }
)
foreach ($case in $cases) {
    $actual = [SmartFormat.Smart]::Format('{1:list:0|、|和}', [object[]]@('unused', $case.Items))
    if ($actual -ne $case.Expected) { throw "List format mismatch: $actual" }
    $checks++
}
Write-Output "$checks runtime formatter checks passed using the installed game's SmartFormat.dll."
