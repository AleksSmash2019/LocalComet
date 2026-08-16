param(
    [int]$WindowHandle
)

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$WindowHandle)
if ($null -eq $root) { throw "Window handle not found" }
$condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::IsControlElementProperty, $true)
$items = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
foreach ($item in $items) {
    $name = $item.Current.Name
    $id = $item.Current.AutomationId
    $type = $item.Current.ControlType.ProgrammaticName
    $enabled = $item.Current.IsEnabled
    $offscreen = $item.Current.IsOffscreen
    if ($name -or $id) {
        Write-Output ("TYPE={0}|NAME={1}|ID={2}|ENABLED={3}|OFFSCREEN={4}" -f $type,$name,$id,$enabled,$offscreen)
    }
}
