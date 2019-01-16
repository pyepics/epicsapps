import time
from lib.pyspin_camera import PySpinCamera
import PySpin
cam = PySpinCamera()
cam.StartCapture()

cam.SetWhiteBalance(0.6, 1.1, auto=True)
print(" Set OK  ")
time.sleep(0.5)


wb_auto = PySpin.CEnumerationPtr(cam.nodemap.GetNode('BalanceWhiteAuto'))

print( "white balance: ",  cam.GetWhiteBalance())
