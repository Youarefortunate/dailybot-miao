Set WshShell = CreateObject("WScript.Shell")
' 获取当前脚本所在目录
strPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
' 运行同目录下的 run_scheduler.bat，参数 0 表示隐藏窗口，False 表示不等待结束
WshShell.Run """" & strPath & "run_scheduler.bat""", 0, False
