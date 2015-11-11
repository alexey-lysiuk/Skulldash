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


if sys.hexversion < 0x3000000:
    range = xrange


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


def _is_doomsound(data):
    sound = io.BytesIO(data)

    try:
        # validate header
        format_num, sample_rate = struct.unpack('<2H', sound.read(4))

        if 3 != format_num:
            # only PCM sound format is supported
            return False

        rates = (8000, 11025, 22050, 44100, 48000)
        return sample_rate in rates

    except:
        return False


def _is_mp3(data):
    sound = io.BytesIO(data)

    try:
        # validate header
        # based on https://github.com/threatstack/libmagic/blob/master/magic/Magdir/animation
        header = struct.unpack('>HB', sound.read(3))

        if 0xFFFA != header[0] & 0xFFFE:
            # wrong version
            return False

        bitrate = header[1] >> 4
        if 0 == bitrate or 15 == bitrate:
            # unused values, wrong bit rate
            return False

        if 0xC == header[1] & 0xC:
            # unused value, wrong sampling rate
            return False

        return True

    except:
        return False


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

        for _ in range(width):
            offset = struct.unpack('<I', pic.read(4))

            if data_size <= offset[0]:
                return False

        return True

    except:
        return False


def _load_pnames(data):
    pnames = io.BytesIO(data)

    count = struct.unpack('<I', pnames.read(4))[0]
    patches = []

    for _ in range(count):
        # read patch name and strip null character(s) with possible junk in unused bytes
        patch = struct.unpack('8s', pnames.read(8))
        patch = patch[0].split('\x00')[0]
        patches.append(patch)

    return patches


_texdefs = {}


def _load_texturex(data, patches, nulltex):
    textures = io.BytesIO(data)

    count = struct.unpack('<I', textures.read(4))[0]
    offsets = []

    for _ in range(count):
        offset = struct.unpack('<I', textures.read(4))[0]
        offsets.append(offset)

    # From http://zdoom.org/wiki/TEXTUREx:
    # A single texture can be redefined by a later TEXTUREx lump,
    # however if a texture is defined more than once in the same TEXTUREx lump,
    # the later definitions are skipped.
    # In other words, a texture uses its first definition in the last lump.

    texdefs = {}

    for offset in offsets:
        textures.seek(offset, io.SEEK_SET)

        name, flags = struct.unpack('<8sH', textures.read(10))

        nullpos = name.find('\x00')
        if nullpos > 0:
            name = name[0:nullpos]

        scalex, scaley = struct.unpack('<2B', textures.read(2))
        width, height = struct.unpack('<2H', textures.read(4))
        columndirectory, patchcount = struct.unpack('<IH', textures.read(6))

        texdef = '", {0}, {1}\r\n{{\r\n'.format(width, height)

        if 0 != scalex:
            texdef += '\txscale {0}'.format(scalex / 8.0)

        if 0 != scaley:
            texdef += '\tyscale {0}'.format(scaley / 8.0)

        if 0x8000 == flags:
            texdef += '\tworldpanning\r\n'

        if nulltex:
            texdef += '\tnulltexture\r\n'
            nulltex = False

        for _ in range(patchcount):
            originx, originy, patch = struct.unpack('<3h', textures.read(6))
            stepdir, colormap = struct.unpack('<2h', textures.read(4))

            texdef += '\tpatch "{0}", {1}, {2}\r\n'.format(patches[patch], originx, originy)

        texdef += '}\r\n\r\n'

        if name not in texdefs:
            texdefs[name] = texdef

    _texdefs.update(texdefs)


def _append_text(filename, data):
    with open(filename, 'ab') as f:
        f.seek(0, os.SEEK_END)
        f.write('\r\n' * (2 if f.tell() > 0 else 1))
        f.write(data)


def _create_directory(filename):
    try:
        os.makedirs(os.path.dirname(filename))
    except:
        pass


def _process_wad(pk3, entry, outpath):
    def _process_textures():
        pnames_lump = wad.find('PNAMES')
        texture1_lump = wad.find('TEXTURE1')

        if not pnames_lump and not texture1_lump:
            return

        patches = _load_pnames(pnames_lump.data)
        _load_texturex(texture1_lump.data, patches, True)

        wad.removelump(pnames_lump)
        wad.removelump(texture1_lump)

        texture2_lump = wad.find('TEXTURE2')
        if texture2_lump:
            _load_texturex(texture2_lump.data, patches, False)
            wad.removelump(texture2_lump)

    def _extract_lumps(subpath=''):
        path = outpath + '/'
        has_subpath = len(subpath) > 0

        if has_subpath:
            path += subpath + '/'

        for lump in lumps:
            if lump.marker:
                continue

            ext = _detect_format(lump.name, lump.data)
            filename = lump.name.lower()

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
                elif 'lmp' == ext:
                    # generic lump, more heuristics required
                    if _is_doomsound(lump.data):
                        format_subpath = 'sounds/'
                    elif _is_mp3(lump.data):
                        format_subpath = 'music/'
                        ext = 'mp3'
                    elif _is_doompic(lump.data):
                        format_subpath = 'graphics/'

                filename = path + format_subpath + filename

            filename += '.' + ext

            if os.path.exists(filename):
                if 'txt' == ext:
                    print('Info: merging content with file ' + filename)

                    _append_text(filename, lump.data)
                    continue
                else:
                    print('Warning: overwriting file ' + filename)
            else:
                _create_directory(filename)

            open(filename, 'wb').write(lump.data)

    def _save_map_wad():
        map_wad = doomwad.WadFile()

        for lump in lumps:
            map_wad.append(lump)

        filename = outpath + '/maps/' + namespace.lower() + '.wad'
        if os.path.exists(filename):
            print('Warning: overwriting already existed file ' + filename)
        else:
            _create_directory(filename)

        map_wad.writeto(open(filename, 'wb'))

    wad_data = pk3.read(entry)
    wad = doomwad.WadFile(wad_data)

    _process_textures()

    PREFIX_TO_SUBDIR = (
        ('A', 'acs'),
        ('F', 'flats'),
        ('P', 'patches'),
        ('S', 'sprites'),
        ('TX', 'textures'),
        # TODO: other namespaces
    )

    for namespace in wad.namespaces():
        lumps = wad.namespacelumps(namespace)

        if 0 == len(namespace):  # global namespace
            _extract_lumps()
        elif not namespace.endswith('_START'):
            _save_map_wad()
        else:
            for p2s in PREFIX_TO_SUBDIR:
                if namespace.endswith(p2s[0] + '_START'):
                    _extract_lumps(p2s[1])
                    break


def extract(filename, outpath):
    _texdefs.clear()

    pk3 = zipfile.ZipFile(filename)

    for entry in pk3.infolist():
        if not entry.filename.lower().endswith('.wad'):
            continue
        _process_wad(pk3, entry, outpath)

    if len(_texdefs) > 0:
        textures = ''

        for name in sorted(_texdefs):
            textures += 'texture "' + name + _texdefs[name]

        _append_text(outpath + '/textures.txt', textures)


def main():
    argc = len(sys.argv)

    if argc < 2 or argc > 3:
        print('Usage: ' + __file__ + ' file.pk3 [output-path]')
        exit(1)

    inpath = sys.argv[1]
    outpath = sys.argv[2] if 3 == argc else os.path.splitext(inpath)[0]

    extract(inpath, outpath)


if __name__ == '__main__':
    main()
