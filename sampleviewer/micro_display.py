from lib import ViewerApp
inifile = 'ide_station.ini'
inifile = 'gsecars_ide.ini'

app = ViewerApp(debug=True, inifile=inifile)
app.MainLoop()
