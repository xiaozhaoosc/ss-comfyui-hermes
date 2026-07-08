<#
.SYNOPSIS
    Batch cleanup merged feature branches (local + remote) by date and number.
.DESCRIPTION
    Branch naming format: yyyy_MM_dd_NNN_description (e.g. 2026_07_08_001_init)
    Only deletes branches already merged into dev_202607. Protects base branches.
    Dry-run by default. Add -Execute to actually delete.
.PARAMETER Date
    Date filter: "2026_07_08" / "2026_07" / "2026" / "*"
    "*" means any date.
.PARAMETER Number
    Number filter: "001" / "001-005" / "*" / ""
    "*" or "" means any number.
.PARAMETER Execute
    Actually perform deletion (default is preview only).
.EXAMPLE
    .\scripts\cleanup_branches.ps1 -Date "2026_07_08"
.EXAMPLE
    .\scripts\cleanup_branches.ps1 -Date "2026_07" -Number "001-005"
.EXAMPLE
    .\scripts\cleanup_branches.ps1 -Date "2026" -Execute
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$Date,
    [string]$Number = "*",
    [switch]$Execute
)

# Protected branches - never delete
$ProtectedBranches = @(
    "main", "master", "dev", "dev_202607",
    "dev_202608", "dev_202609", "dev_202610", "dev_202611", "dev_202612",
    "feat-install-global-skills-UJXbY9"
)

$ErrorActionPreference = "Stop"

function Test-BranchMerged {
    param([string]$BranchName)
    $result = git branch --merged dev_202607 2>$null | Select-String -SimpleMatch $BranchName
    return [bool]$result
}

function Get-BranchInfo {
    param([string]$BranchName)
    $merged = Test-BranchMerged -BranchName $BranchName
    $lastCommit = git log -1 --format="%h %s (%cr)" $BranchName 2>$null
    return @{ Merged = $merged; LastCommit = $lastCommit }
}

function Test-NumberMatch {
    param([string]$BranchNum, [string]$Pattern)
    if ($Pattern -eq "*" -or [string]::IsNullOrEmpty($Pattern)) { return $true }
    if ($Pattern -match "^(\d+)-(\d+)$") {
        $start = [int]$Matches[1]; $end = [int]$Matches[2]
        $num = [int]$BranchNum
        return ($num -ge $start -and $num -le $end)
    }
    return $BranchNum -eq $Pattern
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Feature Branch Cleanup Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Date filter:   $Date"
Write-Host "Number filter: $Number"
$modeStr = if ($Execute) { "EXECUTE" } else { "PREVIEW (dry-run)" }
Write-Host "Mode:          $modeStr" -ForegroundColor $(if ($Execute) {'Red'} else {'Yellow'})
Write-Host ""

# Get all local branches, exclude protected
$allBranches = git branch --format="%(refname:short)" | Where-Object { $_ -notin $ProtectedBranches }

# Match feature branches with naming format
# Supports both "2026_07_08_001_desc" and "2026年07月08日_001_desc"
$candidates = @()
foreach ($b in $allBranches) {
    # Try both formats: numeric and Chinese
    $matched = $false
    $bDate = ""; $bNum = ""; $bDesc = ""

    # Format A: 2026_07_08_001_desc
    if ($b -match "^(\d{4})_(\d{2})_(\d{2})_(\d{3})_(.+)$") {
        $bDate = "$($Matches[1])_$($Matches[2])_$($Matches[3])"
        $bNum = $Matches[4]; $bDesc = $Matches[5]
        $matched = $true
    }
    # Format B: 2026年07月08日_001_desc (Chinese date via Unicode escapes)
    # 年=\u5e74 月=\u6708 日=\u65e5
    elseif ($b -match "^(\d{4})\u5e74(\d{2})\u6708(\d{2})\u65e5_(\d{3})_(.+)$") {
        $bDate = "$($Matches[1])_$($Matches[2])_$($Matches[3])"
        $bNum = $Matches[4]; $bDesc = $Matches[5]
        $matched = $true
    }

    # Broader fallback: any branch with _NNN_ pattern after a date-like prefix
    if (-not $matched -and $b -match "_(\d{3})_") {
        $bNum = $Matches[1]
        $bDesc = $b
        $bDate = ""
        $matched = $true
    }

    if (-not $matched) { continue }

    # Date matching
    $dateMatch = $false
    if ($Date -eq "*") {
        $dateMatch = $true
    } elseif ($bDate -ne "") {
        if ($Date -match "^\d{4}_\d{2}_\d{2}$") {
            $dateMatch = ($bDate -eq $Date)
        } elseif ($Date -match "^\d{4}_\d{2}$") {
            $dateMatch = ($bDate -like "$Date*")
        } elseif ($Date -match "^\d{4}$") {
            $dateMatch = ($bDate -like "$Date*")
        }
    } else {
        # No parseable date on branch, only match if Date is "*"
        $dateMatch = ($Date -eq "*")
    }

    $numMatch = Test-NumberMatch -BranchNum $bNum -Pattern $Number

    if ($dateMatch -and $numMatch) {
        $info = Get-BranchInfo -BranchName $b
        $candidates += [PSCustomObject]@{
            Branch = $b
            Date = $bDate
            Num = $bNum
            Desc = $bDesc
            Merged = $info.Merged
            LastCommit = $info.LastCommit
        }
    }
}

if ($candidates.Count -eq 0) {
    Write-Host "No matching feature branches found." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Hint: branch naming format should be 'yyyy_MM_dd_NNN_description'"
    exit 0
}

Write-Host "Matched $($candidates.Count) branch(es):" -ForegroundColor Green
Write-Host ""
$candidates | Format-Table Branch, @{N='Merged';E={if($_.Merged){'YES'}else{'NO'}}}, LastCommit -AutoSize
Write-Host ""

$mergedBranches = $candidates | Where-Object { $_.Merged }
$unmergedBranches = $candidates | Where-Object { -not $_.Merged }

Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Merged (deletable):  $($mergedBranches.Count)"
Write-Host "  Unmerged (skip):     $($unmergedBranches.Count)"
Write-Host ""

if ($unmergedBranches.Count -gt 0) {
    Write-Host "WARNING: following branches NOT merged into dev_202607, will skip:" -ForegroundColor Yellow
    $unmergedBranches | ForEach-Object { Write-Host "  - $($_.Branch)" }
    Write-Host ""
}

if (-not $Execute) {
    Write-Host "[PREVIEW] Above merged branches would be deleted (local + remote)." -ForegroundColor Yellow
    Write-Host "To actually delete, add -Execute:"
    Write-Host "  .\scripts\cleanup_branches.ps1 -Date `"$Date`" -Number `"$Number`" -Execute" -ForegroundColor Cyan
    exit 0
}

if ($mergedBranches.Count -eq 0) {
    Write-Host "No merged branches to delete." -ForegroundColor Yellow
    exit 0
}

Write-Host "Deleting merged branches..." -ForegroundColor Cyan
$deleted = 0; $failed = 0
foreach ($b in $mergedBranches) {
    Write-Host ""
    Write-Host "Delete: $($b.Branch)" -ForegroundColor Yellow

    # Delete local branch (-d is safe: only deletes merged)
    $localResult = git branch -d $b.Branch 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] local deleted" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] local delete failed (maybe already gone): $localResult" -ForegroundColor Yellow
    }

    # Delete remote branch
    $remoteResult = git push origin --delete $b.Branch 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] remote deleted" -ForegroundColor Green
        $deleted++
    } else {
        Write-Host "  [WARN] remote delete failed (maybe not exists): $remoteResult" -ForegroundColor Yellow
        $failed++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Cleanup Done" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Success: $deleted"
Write-Host "Failed:  $failed"
