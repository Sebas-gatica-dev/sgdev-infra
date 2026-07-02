param(
  [ValidateSet('init', 'fmt', 'validate', 'plan', 'apply', 'destroy')]
  [string]$Action = 'plan',
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$TerraformArgs
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')
$terraformDir = Join-Path $root 'terraform'

Push-Location $terraformDir
try {
  switch ($Action) {
    'init' {
      terraform init @TerraformArgs
    }
    'fmt' {
      terraform fmt -recursive @TerraformArgs
    }
    'validate' {
      terraform init -backend=false
      terraform validate @TerraformArgs
    }
    'plan' {
      terraform init
      terraform plan @TerraformArgs
    }
    'apply' {
      terraform init
      terraform apply @TerraformArgs
    }
    'destroy' {
      terraform init
      terraform destroy @TerraformArgs
    }
  }
} finally {
  Pop-Location
}
