#!/usr/bin/env python

#
# Tools for Skulldash
# Copyright (C) 2015 Alexey Lysiuk
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import shutil
import sys

if sys.hexversion < 0x2070000 or 0x3000000 <= sys.hexversion < 0x3020000:
    print('This script requires Python 2.7 or Python 3.2 and higher')
    exit(1)

# all sources are in lib directory
sys.path[0] = os.path.dirname(os.path.abspath(__file__)) + '/lib'

import unpk3


def main():
    argc = len(sys.argv)
    standalone = True

    if 1 == argc:
        print('No skulldash.pk3 specified, building add-on version...')
        standalone = False
    elif 2 == argc:
        print('Building standalone version...')
    else:
        print('Usage: ' + __file__ + ' [skulldash.pk3]')
        exit(1)

    root_path = os.path.dirname(__file__)
    root_path = os.path.abspath(root_path) + os.sep

    work_path = root_path + 'tmp/~skulldash~'
    shutil.rmtree(work_path, True)

    shutil.copytree(root_path + 'data', work_path)

    if standalone:
        unpk3.extract(sys.argv[1], work_path)

    temp_archive_path = shutil.make_archive(root_path + '~skulldash~', 'zip', work_path)
    archive_path = '{0}skulldash_zdoom_{1}.pk3'.format(root_path, 'standalone' if standalone else 'addon')

    try:
        os.remove(archive_path)
    except:
        pass

    shutil.move(temp_archive_path, archive_path)

    shutil.rmtree(work_path, True)

if __name__ == '__main__':
    main()

