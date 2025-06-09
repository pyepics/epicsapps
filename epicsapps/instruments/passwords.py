#
import time
from os import urandom
from hashlib import pbkdf2_hmac
from base64 import b64encode

__all__ = ('hash_password', 'test_password')

def b64(s, size=64):
    return b64encode(s).decode('ascii').replace('/', '_')[:size]

def random_salt(size=16):
    return b64(urandom(size), size=size)

def hash_password(password, salt=None, iterations=147623, hash_name='sha512'):
    """hash a password to a hashed string that can be saved
    and then used to test password
    """
    if salt is None:
        salt = random_salt()
    pwhash = b64(pbkdf2_hmac(hash_name, password.encode('ascii'),
                             salt.encode('ascii'), iterations))
    return '&'.join([hash_name, f'{iterations:07d}', salt, pwhash])

def test_password(password, hash):
    """test whether password matches hash"""
    test = '*&*'
    if hash is not None and '&' in hash:
        try:
            name, iter, salt, pwhash = hash.split('&')
            test = hash_password(password, salt=salt,
                                 iterations=int(iter),
                                 hash_name=name)
        except:
            test = '*&*'
    return hash == test

if __name__ == '__main__':
    t0 = time.time()
    pw = 'freshly orange violins'
    hash = hash_password(pw)
    print(f"run time {(time.time()-t0):.3f}")
    print(test_password(pw, hash))
