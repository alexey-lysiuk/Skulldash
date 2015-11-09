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

import io
import os
import struct
import sys
import shutil
import zipfile

import doomwad


def _prepare_outdir(path):
    # TODO: simplifies debugging, remove this later!
    try:
        shutil.rmtree(path)
    except:
        pass

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


_TEXTLUMP_NAMES = (
    'ANIMDEFS',
    'DECALDEF',
    'DECORATE',
    'GAMEINFO',
    'GLDEFS',
    'HIRESTEX',
    'LOADACS',
    'MAPINFO',
    'SBARINFO',
    'SNDINFO',
    # TODO: add remaining names
)


def _detect_format(name, data):
    # texts, merge-able
    if name in _TEXTLUMP_NAMES:
        return 'txt'

    # ACS binary code
    elif data.startswith('ACS'):
        return 'o'

    # images
    elif '\xFF\xD8\xFF\xE0' == data[0:4] and 'JFIF' == data[6:10]:
        return 'jpg'
    elif data.startswith('\x89PNG'):
        return 'png'

    # music
    elif data.startswith('MThd'):
        return 'mid'
    elif data.startswith('MUS'):
        return 'mus'
    elif data.startswith('Extended Module:'):
        return 'xm'

    # sounds
    elif data.startswith('OggS'):
        return 'ogg'
    elif data.startswith('RIFF'):
        # TODO: additional format check
        return 'wav'

    # generic lump
    else:
        return 'lmp'


def _is_doompic(data):
    pic = io.BytesIO(data)

    try:
        # validate header
        width, height, left, top = struct.unpack('<2H2h', pic.read(8))
        limit = 2048  # guess value

        if width > limit or height > limit or left > limit or top > limit:
            return False

        # validate columns data
        data_size = len(data)

        for i in range(width):
            offset = struct.unpack('<I', pic.read(4))

            if data_size <= offset[0]:
                return False

        return True

    except:
        return False


def _process_wad(pk3, entry, outpath):
    def _extract_lumps(subpath=''):
        path = outpath + '/'
        has_subpath = len(subpath) > 0

        if has_subpath:
            path += subpath + '/'

        for lump in lumps:
            if lump.marker:
                continue

            ext = _detect_format(lump.name, lump.data)
            filename = lump.name.lower() + '.' + ext

            if has_subpath:
                filename = path + filename
            else:
                format_subpath = ''

                if 'png' == ext or 'jpg' == ext:
                    format_subpath = 'graphics/'
                elif 'mid' == ext or 'mus' == ext or 'xm' == ext:
                    format_subpath = 'music/'
                elif 'ogg' == ext or 'wav' == ext:
                    format_subpath = 'sounds/'
                elif 'lmp' == ext and _is_doompic(lump.data):
                    format_subpath = 'graphics/'

                filename = path + format_subpath + filename

            if os.path.exists(filename):
                if 'txt' == ext:
                    print('Info: merging content with file ' + filename)

                    with open(filename, 'ab') as f:
                        f.seek(0, os.SEEK_END)
                        f.write('\r\n' * 2)
                        f.write(lump.data)
                    return
                # TODO: merging for PNAMES and TEXTUREx
                else:
                    print('Warning: overwriting file ' + filename)

            open(filename, 'wb').write(lump.data)

    def _save_map_wad():
        map_wad = doomwad.WadFile()

        for lump in lumps:
            map_wad.append(lump)

        filename = outpath + '/maps/' + namespace.lower() + '.wad'
        if os.path.exists(filename):
            print('Warning: overwriting already existed file ' + filename)

        map_wad.writeto(open(filename, 'wb'))

    wad_data = pk3.read(entry)
    wad = doomwad.WadFile(wad_data)

    for namespace in wad.namespaces():
        lumps = wad.namespacelumps(namespace)

        if 0 == len(namespace):  # global namespace
            _extract_lumps()
        elif 'A_START' == namespace:
            _extract_lumps('acs')
        elif 'TX_START' == namespace:
            _extract_lumps('textures')
        elif namespace.endswith('F_START'):
            _extract_lumps('flats')
        elif namespace.endswith('S_START'):
            _extract_lumps('sprites')
        # TODO: other namespaces
        elif not namespace.endswith('_START'):
            _save_map_wad()


def main():
    argc = len(sys.argv)

    if argc < 2 or argc > 3:
        print('Usage: ' + __file__ + ' file.pk3 [output-path]')
        exit(1)

    inpath = sys.argv[1]
    outpath = sys.argv[2] if 3 == argc else os.path.splitext(inpath)[0]

    pk3 = zipfile.ZipFile(inpath)
    _prepare_outdir(outpath)

    for entry in pk3.infolist():
        if not entry.filename.lower().endswith('.wad'):
            continue
        _process_wad(pk3, entry, outpath)


if __name__ == '__main__':
    main()
