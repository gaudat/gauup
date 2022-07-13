import sys
import os
import zipfile

INSTALL_PREFIX = '/usr/local/bin'
GALLERY_DL_LOCATION = INSTALL_PREFIX + '/gallery-dl'

NEW_WHEEL_LOCATION = sys.argv[1]	


try:
    with zipfile.ZipFile(NEW_WHEEL_LOCATION) as zf:
        pass
except Exception:
    raise RuntimeError("Supplied wheel file is invalid")

TEMP_OUTPUT = INSTALL_PREFIX + '/gallery-dl.new'

with open(TEMP_OUTPUT, 'wb') as of, open(NEW_WHEEL_LOCATION, 'rb') as zf:
    of.write(b'#!/usr/bin/env python3\n')
    CHUNK_SIZE = 65536
    chunk = zf.read(CHUNK_SIZE)
    while len(chunk) > 0:
        of.write(chunk)
        chunk = zf.read(CHUNK_SIZE)

MAIN_PY_CONTENT = """\
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2017-2019 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

import sys

if __package__ is None and not hasattr(sys, "frozen"):
    import os.path
    path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.realpath(path))

import gallery_dl

if __name__ == "__main__":
    sys.exit(gallery_dl.main())
"""

with zipfile.ZipFile(TEMP_OUTPUT, 'a') as zf:
    with zf.open('__main__.py', 'w') as mf:
        mf.write(MAIN_PY_CONTENT.encode('utf-8'))

os.chmod(TEMP_OUTPUT, 0o755)
os.unlink(GALLERY_DL_LOCATION)
os.rename(TEMP_OUTPUT, GALLERY_DL_LOCATION)

