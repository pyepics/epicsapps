import os
from epics_sampleviewer import ViewerApp

inifile = 'SampleStage_autosave.ini'
workdir_file = '//cars5/Data/xas_user/scan_config/13bmd/bmd_samplestage.dat'

if True:
    f = open(workdir_file, 'r')
    workdir = f.readlines()[0][:-1]
    f.close()
    os.chdir(workdir)
else: # except:
    pass

app = ViewerApp(debug=False, inifile=inifile)
app.MainLoop()
