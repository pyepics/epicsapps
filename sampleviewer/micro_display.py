from gsemicro import ViewerApp
configfile = 'ide_station.ini'

app = ViewerApp(debug=True, inifile=configfile)
app.MainLoop()
