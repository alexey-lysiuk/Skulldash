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
import zipfile
import sys

import doomwad


def prepare_outdir(path):
    os.mkdir(path)
    os.mkdir(path + '/acs')
    os.mkdir(path + '/flats')
    os.mkdir(path + '/graphics')
    os.mkdir(path + '/maps')
    os.mkdir(path + '/music')
    os.mkdir(path + '/patches')
    os.mkdir(path + '/sounds')
    os.mkdir(path + '/sprites')
    os.mkdir(path + '/textures')


def process_wad(pk3, entry, outpath):
    def _extract_lumps(subdir='', ext='lmp'):
        subpath = outpath + '/'

        if len(subdir) > 0:
            subpath += subdir + '/'

        for lump in lumps:
            if lump.marker:
                continue

            with open(subpath + lump.name + '.' + ext, 'wb') as f:
                f.write(lump.data)

    def _save_map_wad():
        map_wad = doomwad.WadFile()

        for lump in lumps:
            map_wad.append(lump)

        with open(outpath + '/maps/' + ns + '.wad', 'wb') as f:
            map_wad.writeto(f)

    wad_data = pk3.read(entry)
    wad = doomwad.WadFile(wad_data)

    for ns in wad.namespaces():
        lumps = wad.namespacelumps(ns)

        if 0 == len(ns):
            # global namespace
            _extract_lumps()
        elif 'A_START' == ns:
            # ACS code
            _extract_lumps('acs', 'o')
        elif ns.endswith('S_START'):
            # sprites
            _extract_lumps('sprites')
        # TODO: other namespaces
        elif not ns.endswith('_START'):
            # level
            _save_map_wad()


def main():
    argc = len(sys.argv)

    if argc < 2 or argc > 3:
        print('Usage: {0} file.pk3 [output-path]'.format(__file__))
        exit(1)

    inpath = sys.argv[1]
    outpath = sys.argv[2] if 3 == argc else os.path.splitext(inpath)[0]

    pk3 = zipfile.ZipFile(inpath)
    prepare_outdir(outpath)

    for entry in pk3.infolist():
        if not entry.filename.lower().endswith('.wad'):
            continue
        process_wad(pk3, entry, outpath)


if __name__ == '__main__':
    main()
