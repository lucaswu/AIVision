Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = oWS.SpecialFolders("Desktop") & "\AIVision.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "I:\项目\AIVision\AIVision.exe"
oLink.WorkingDirectory = "I:\项目\AIVision"
oLink.IconLocation = "I:\项目\AIVision\model\weld\launcher\app.ico, 0"
oLink.Description = "AIVision Weld Defect Inspection System"
oLink.Save
WScript.Echo "Shortcut created at: " & sLinkFile
