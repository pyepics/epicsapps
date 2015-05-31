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
