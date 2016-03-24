#!/usr/bin/python

# convert SampleStage.html or Microscope.html to
# Positions file

import sys
import json
import HTMLParser
from collections import OrderedDict

class html2pos(HTMLParser.HTMLParser):
    def __init__(self):
        HTMLParser.HTMLParser.__init__(self)
        self.rows = []
        self.row  = OrderedDict()
        self.key = None
        self.in_td = False
        self.in_ahref = False

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
        elif tag == 'a':
            self.in_ahref = True
            self.href =  attrs[0][1]
        elif tag == 'table':
            self.row = OrderedDict()

    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td = False
        elif tag == 'a':
            self.in_ahref = False

        elif tag == 'table':
            if 'Position:' in self.row:
                name = self.row.pop('Position:')
                extra = {'Date:': self.row.pop('Date')}
                extra['image'] = self.href
                data = list(self.row.items())
                self.rows.append(json.dumps([name, data, extra]))
            self.row = OrderedDict()

    def handle_data(self, data):
        if self.in_td:
            dat = data.strip().replace('\t',' ').replace('\n','').replace('\r','')
            if self.key is not None:
                self.row[self.key] = dat
                if self.key.startswith('Position'):
                    self.key = 'Date'
                else:
                    self.key = None
            if dat.startswith('Position') or dat.startswith('13XRM'):
                self.key = dat
            if self.in_ahref:
                self.row['href'] = self.href

if __name__ == "__main__":
    for htmlfile in sys.argv[1:]:
        outfile = htmlfile.replace('.html', '.pos')
        parser = html2pos()
        fh = open(htmlfile, 'r')
        parser.feed(fh.read())
        fh.close()

        buff = ["#SampleViewer POSITIONS FILE v1.0"]
        buff.extend( parser.rows)
        buff.append('')
        fh = open(outfile, 'w')
        fh.write("\n".join(buff))
        fh.close()
