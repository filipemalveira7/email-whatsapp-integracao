' run_hidden.vbs — inicia email_monitor.py sem nenhuma janela visível.
' Usado pela tarefa agendada "AgenteWhatsApp-EmailMonitor" (Task Scheduler).
' Saída (prints/erros) vai pra logs\monitor.log.
Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = "D:\OneDrive - REDEPRIME\Documents\Centro Integrado - Fortaleza\Filipe Malveira\agente wpp"
' Espera o processo terminar (True) pra que o Agendador de Tarefas veja o wscript
' "vivo" durante toda a execução e consiga reiniciar sozinho se o monitor cair.
exitCode = objShell.Run("cmd /c ""C:\Users\CCI 01\AppData\Local\Python\pythoncore-3.14-64\python.exe"" -u -X utf8 email_monitor.py >> logs\monitor.log 2>&1", 0, True)
WScript.Quit(exitCode)
