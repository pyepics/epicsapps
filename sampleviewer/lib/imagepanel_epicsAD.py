            cname = "%s%s1:"% (self.cam_adpref, self.cam_adform.upper())
            caput("%sFileName" % cname, fname, wait=True)
            time.sleep(0.03)
            caput("%sWriteFile" % cname, 1, wait=True)
            time.sleep(0.05)
            img_ok = False
            t0 = time.time()
            while not img_ok:
                if time.time()-t0 > 15:
                    break
                try:
                    out = open(fname, "rb")
                    imgdata = base64.b64encode(out.read())
                    out.close()
                    img_ok = True
                except:
                    pass
                time.sleep(0.05)

    @EpicsFunction
    def Start(self):
        if not self.cam_adpref.endswith(':'):
            self.cam_adpref = "%s:" % self.cam_adpref
        cname = "%s%s1:"% (self.cam_adpref, self.cam_adform.upper())
        caput("%sEnableCallbacks" % cname, 1)
        thisdir = os.path.abspath(os.getcwd())
        thisdir = thisdir.replace('\\', '/').replace('T:/', '/Volumes/Data/')

        caput("%sFilePath" % cname, thisdir)
        caput("%sAutoSave" % cname, 0)
        caput("%sAutoIncrement" % cname, 0)
        caput("%sFileTemplate" % cname, "%s%s")
        if self.cam_adform.upper() == 'JPEG':
            caput("%sJPEGQuality" % cname, 90)
