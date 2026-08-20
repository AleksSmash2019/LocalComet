$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, 'LocalComet')
$window = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $condition)
if (-not $window) { Write-Output 'WINDOW_NOT_FOUND'; exit 0 }
$nodes = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
Write-Output ("WINDOW=" + $window.Current.Name + " COUNT=" + $nodes.Count)
foreach ($node in $nodes) {
  $name = $node.Current.Name
  $type = $node.Current.ControlType.ProgrammaticName
  $id = $node.Current.AutomationId
  if ($name -or $id) {
    Write-Output ("NAME=" + $name + " TYPE=" + $type + " ID=" + $id + " ENABLED=" + $node.Current.IsEnabled)
  }
}
