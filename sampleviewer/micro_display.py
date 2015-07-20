import os
from lib import ViewerApp
#inifile = 'ide_station.ini'
#inifile = 'gsecars_ad.ini'
#inifile = 'SampleStage_autosave.ini'

inifile = 'SampleStage_autosave.ini'
workdir_file = '//cars5/Data/xas_user/scan_config/13ide/samplestage.dat'

try:
    f = open(workdir_file, 'r')
    workdir = f.readlines()[0][:-1]
    f.close()
    os.chdir(workdir)
except:
    pass

app = ViewerApp(debug=False, inifile=inifile)
app.MainLoop()


try:
    f = open(workdir_file, 'w')
    f.write("%s\n" % os.getcwd())
    f.close()
except:
    pass
