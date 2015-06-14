from lib import ViewerApp
inifile = 'ide_station.ini'
inifile = 'sample.ini'

app = ViewerApp(debug=True, inifile=inifile)
app.MainLoop()
