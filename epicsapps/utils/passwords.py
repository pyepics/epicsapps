import wx
import time
from os import urandom
from base64 import b64encode
from hashlib import pbkdf2_hmac

from collections import namedtuple

from wxutils import (Button, CEN, Check, Choice, EditableListBox, OkCancel,
                     FRAMESTYLE, FileOpen, FileSave, FloatCtrl, FloatSpin,
                     Font, COLORS, set_color, GridPanel, LabeledTextCtrl, HLine,
                     HyperText, LEFT, MenuItem, Popup, RIGHT, RowPanel,
                     SimpleText, TextCtrl, get_icon, pack,
                     BitmapButton, ToggleButton, YesNo, NumericCombo,
                     make_steps)

def b64(inp):
    "base64 endcode a bytes array"
    return b64encode(inp).decode('ascii').replace('/', '_')

def random_salt(size=37):
    return b64(urandom(2*size))[:size]

def hash_password(password, salt=None, iterations=391939, hash_name='sha512'):
    """hash a password to a hashed string that can be saved

    and then used to test the password with `test_password()`

    the resulting hash should be a strong hash that can be stored to
    disk without high risk of brute-force attack.  By default, it uses a
    randomly generated 37-character salt, minimizing the likliehood of
    existing rainbow tables.  The hashing uses `pbdkf2_hmac()` with
    'sha512' and the generated salt and a large number (default 93719)
    of iterations to deliberately slow down computation time.  On CPUs
    from 2025, this function should take at least 100 ms to run.
    """
    if salt is None:
        salt = random_salt()
    pwhash = b64(pbkdf2_hmac(hash_name, password.encode('ascii'),
                             salt.encode('ascii'), iterations))
    return '&'.join([hash_name, f'{iterations:d}', salt, pwhash])

def test_password(password, pwhash):
    """test whether password matches a hash, as set with `hash_password()`"""
    test_hash, result = '', None
    if pwhash is not None and '&' in pwhash:
        try:
            hash_name, iterations, salt, result = pwhash.split('&')
            test_hash = b64(pbkdf2_hmac(hash_name, password.encode('ascii'),
                                      salt.encode('ascii'), int(iterations)))
        except:
            pass
    return len(test_hash)> 55 and (result == test_hash)


__LOWER = 'abcdefghijklmnopqrstuvwxyz'
__UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
__DIGITS = '0123456789'
__SPECIAL = ';~,`!%$$&^?*#:"/|(){}[]<>\'\\'

def password_rules(pwtest, minlen=8, lowercase=1, uppercase=1, digits=1, special=1,
                   invalid=''):
    """check password rules for minimum lenghth, number of lower, upper case letters,
       digits, special characters and avoiding invalid characters

    Arguments:
    -----------
     pwtest     str, password to test, required
     minlen     int, minimum length [8]
     lowercase  int, minimum number of lower case letters [1]
     uppercase  int, minimum number of upper case letters [1]
     digiits    int, minimum number of digits [1]
     special    int, minimum number of special characters [1]
     invalid    str, string containing invalid characters  ''
    """
    if len(pwtest) < minlen:
        return False, f'must be at least {minlen} characters'
    lc, uc, di, sp = 0, 0, 0, 0
    if invalid is None:
       invalid = ''

    for x in pwtest:
        if x in __LOWER:
            lc += 1
        elif x in __UPPER:
            uc += 1
        elif x in __DIGITS:
            di += 1
        elif x in __SPECIAL:
            sp += 1
        if x in invalid:
            return False, f"cannont contain characters in '{invalid}'."

    if lc < lowercase:
        return False, f'must be at least {lowercase} lower case letters.'
    if uc < uppercase:
        return False, f'must be at least {uppercase} upper case letters.'
    if sp < special:
        return False, f'must be at least {special} special characters.'
    if di < digits:
        return False, f'must be at least {digits} digits.'
    return True, 'password conforms to rules'

class PasswordCheckDialog(wx.Dialog):
    """Check Password"""
    def __init__(self, parent=None, pwhash='_'):
        self.pwhash = pwhash
        self.valid = False
        wx.Dialog.__init__(self, parent, wx.ID_ANY, size=(650, 350),
                           title='Check Password')

        panel = GridPanel(self, itemstyle=wx.ALIGN_LEFT)

        panel.Add(SimpleText(panel, ' Enter Password:'), dcol=1, newrow=True)
        self.pwtext = TextCtrl(panel, '', style=wx.TE_PASSWORD,
                               size=(175, -1), act_on_losefocus=False,
                               action=self.onCheck)
        test = Button(panel, label='Check ', size=(175, -1), action=self.onCheck)
        panel.Add(self.pwtext, dcol=1, newrow=False)
        panel.Add(test, dcol=1, newrow=True)
        self.msg = SimpleText(panel, '', size=(200, -1))
        panel.Add(self.msg, dcol=2, newrow=False)
        panel.Add(HLine(panel, size=(300, -1)), dcol=2, newrow=True)

        btnsizer = wx.StdDialogButtonSizer()
        btnsizer.AddButton(wx.Button(panel, wx.ID_OK))
        btnsizer.AddButton(wx.Button(panel, wx.ID_CANCEL))
        btnsizer.Realize()

        panel.Add(btnsizer, dcol=2, newrow=True)
        panel.pack()

    def onCheck(self, event=None):
        self.valid = test_password(self.pwtext.GetValue(), self.pwhash)
        if not self.valid:
            self.msg.SetLabel('password incorrect')
        else:
            self.msg.SetLabel('password matches')

    def GetResponse(self, newname=None):
        self.Raise()
        self.valid = False
        if wx.ID_OK == self.ShowModal():
            self.onCheck()
        return self.valid

class PasswordSetDialog(wx.Dialog):
    """Dialog to Set Password, including
         type password twice to check that they match
         optional change-from-current-password
         enforce common password rules on length, special chars, etc.

    call with:
        dlg = PasswordSetDialog(parent, current_hash, msg='Set Password')
        result = dlg.GetResponse()

    where `current_hash` is an existing hashed (returned from a previous call,
    saved, or generated from `hash_password()`).  If not empty, that password
    will have to be validated to change an existing password to a new one.

    the dlt.GetResponse() call will show the Modal (blocking) Dialog and
    return the new password hash.  If this is shorter than 30 characters,
    it should be considered invalid.

    Password Rules can be specified with a `rules` dictionary, which defaults too:
          rules={'minlen': 8, 'lowercase': 1, 'uppercase': 1, 'digits': 1,
                 'special': 1, 'invalid': ''}
    giving minimum length, number of lower, upper case, digits, and special characters,
    where special characters are
           ; ~ , ` ! % $ $ & ^ ? * # : " / | ( ) { } [ ] < >  ' \

    note that '_' and '-' are allowed but do not count as special characters.
    if 'invalid' is not empty, the password cannot contain any of those characters.

    """
    def __init__(self, parent=None, current_hash='',  msg='Set Password',
                rules={'minlen': 8, 'lowercase': 1, 'uppercase': 1, 'digits': 1,
                       'special': 1, 'invalid': ''}):
        if current_hash is None:
            current_hash = ''
        self.current_hash = current_hash
        self.pwhash = ''
        self.rules = rules

        wx.Dialog.__init__(self, parent, wx.ID_ANY, size=(650, 350),
                           title=msg)

        panel = GridPanel(self, ncols=5, nrows=6, pad=3,
                          itemstyle=wx.ALIGN_LEFT)

        if len(self.current_hash) > 30:
            panel.Add(SimpleText(panel, ' Enter Current Password:'), dcol=1, newrow=True)

            self.currpw = TextCtrl(panel, '', style=wx.TE_PASSWORD, size=(175, -1))
            panel.Add(self.currpw, dcol=1, newrow=False)
            panel.Add(HLine(panel, size=(300, -1)), dcol=2, newrow=True)

        self.pw1 = TextCtrl(panel, '', style=wx.TE_PASSWORD, size=(175, -1))
        self.pw2 = TextCtrl(panel, '', style=wx.TE_PASSWORD, size=(175, -1))
        test = Button(panel, label='Check ', size=(175, -1), action=self.onCheck)
        self.msg = SimpleText(panel, ' ', size=(200, -1))


        panel.Add(SimpleText(panel, ' Enter New Password:'), dcol=1, newrow=True)
        panel.Add(self.pw1, dcol=1, newrow=False)
        panel.Add(SimpleText(panel, ' Repeat Password:'), dcol=1, newrow=True)
        panel.Add(self.pw2, dcol=1, newrow=False)

        panel.Add(test, dcol=1, newrow=True)
        panel.Add(self.msg, dcol=2, newrow=False)

        panel.Add(HLine(panel, size=(300, -1)), dcol=2, newrow=True)

        btnsizer = wx.StdDialogButtonSizer()
        btnsizer.AddButton(wx.Button(panel, wx.ID_OK))
        btnsizer.AddButton(wx.Button(panel, wx.ID_CANCEL))
        btnsizer.Realize()

        panel.Add(btnsizer, dcol=2, newrow=True)
        panel.pack()

    def onCheck(self, event=None):
        self.pwhash = ''
        if len(self.current_hash) > 30:
            curr_valid = test_password(self.currpw.GetValue(), self.current_hash)
        else:
            curr_valid = True
        if not curr_valid:
            self.msg.SetLabel("Current Password is invalid")
            return False
        pw1 = self.pw1.GetValue()
        valid, reason = password_rules(pw1, **self.rules)
        if not valid:
            self.msg.SetLabel(reason)
            return False

        if pw1 != self.pw2.GetValue():
            self.msg.SetLabel("Passwords do not match")
            return False
        else:
            self.msg.SetLabel("Passwords match")
            self.pwhash = hash_password(pw1)

    def GetResponse(self, newname=None):
        self.Raise()
        self.pwhash = ''
        if wx.ID_OK == self.ShowModal():
            self.onCheck()
        return self.pwhash
