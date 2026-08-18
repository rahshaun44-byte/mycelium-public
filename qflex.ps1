param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)
$scriptPath = Join-Path $PSScriptRoot "qflex.py"
python $scriptPath $Args
