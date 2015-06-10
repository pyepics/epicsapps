

imgdata = urlopen(self.cam_weburl).read()
if imgdata is not None:
    out = open(fname, "wb")
    out.write(imgdata)
    out.close()
    imgdata = base64.b64encode(imgdata)
