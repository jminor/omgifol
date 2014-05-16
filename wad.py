import os, glob, collections

from omg import lump, util, palette
from omg.wadio import WadIO

class LumpGroup(collections.OrderedDict):
    """A dict-like object for holding a group of lumps"""

    def __init__(self, name='data', lumptype=lump.Lump, config=()):
        collections.OrderedDict.__init__(self)
        self._name   = name
        self.lumptype = lumptype
        self.config = config
        self.__init2__()

    def __init2__(self):
        pass

    def load(self, filename):
        """Load entries from a WAD file. All lumps from the same
        section in that WAD is loaded (e.g. if this is a patch
        section, all patches in the WAD will be loaded."""
        iw = WAD(); iw.load(filename)
        self._lumps += util.deepcopy(iw.__dict__[self._sect_name]._lumps)

    def to_file(self, filename):
        """Save group as a separate WAD file."""
        w = WadIO(filename)
        self.save_wadio(w)

    def from_glob(self, globpattern):
        """Create lumps from files matching the glob pattern."""
        for p in glob.glob(globpattern):
            name = util.fixname(os.path.basename(p[:p.rfind('.')]))
            self[name] = self.lumptype(from_file=p)

    def save_wadio(self, wadio):
        """Save to a WadIO object."""
        for m in self:
            wadio.insert(m, self[m].data)

    def copy(self):
        """Creates a deep copy."""
        a = self.__class__(self._name, self.lumptype, self.config)
        for k in self:
            a[k] = self[k].copy()
        return a

    def __add__(self, other):
        """Adds two dicts, copying items shallowly"""
        c = self.__class__(self._name, self.lumptype, self.config)
        c.update(self)
        c.update(other)
        return c

class MarkerGroup(LumpGroup):
    """Group for lumps found between markers, e.g. sprites"""

    def __init2__(self):
        self.prefix = self.config + "*_START"
        self.suffix = self.config + "*_END"
        # In case group opens with XX_ and ends with X_
        self.abssuffix = self.config + "_END"

    def load_wadio(self, wadio):
        """Load all matching lumps that have not already
        been flagged as read from the given WadIO object."""
        inside = False
        startedwith, endswith = "", ""
        for i in range(len(wadio.entries)):
            if wadio.entries[i].been_read:
                inside = False
                continue
            name = wadio.entries[i].name
            if inside:
                if util.wccmp(name, endswith) or util.wccmp(name, self.abssuffix):
                    inside = False
                else:
                    if wadio.entries[i].size != 0:
                        self[name] = self.lumptype(wadio.read(i))
                wadio.entries[i].been_read = True
            else:
                # print name, self.prefix, util.wccmp(name, self.prefix)
                if util.wccmp(name, self.prefix):
                    endswith = name.replace("START", "END")
                    inside = True
                    wadio.entries[i].been_read = True

    def save_wadio(self, wadio):
        """Save to a WadIO object."""
        if len(self) == 0:
            return
        wadio.insert(self.prefix.replace('*', ''), '')
        LumpGroup.save_wadio(self, wadio)
        wadio.insert(self.suffix.replace('*', ''), '')


class HeaderGroup(LumpGroup):
    """Group for lumps arranged header-tail (e.g. maps)"""

    def __init2__(self):
        self.headers = self.config[0]
        self.tail = self.config[1]

    def load_wadio(self, wadio):
        """Load all matching lumps that have not already
        been flagged as read from the given WadIO object."""
        numlumps = len(wadio.entries)
        i = 0
        while i < numlumps:
            if wadio.entries[i].been_read:
                i += 1
                continue
            name = wadio.entries[i].name
            added = False
            for head in self.headers:
                if util.wccmp(name, head):
                    added = True
                    self[name] = NameGroup()
                    wadio.entries[i].been_read = True
                    i += 1
                    while i < numlumps and util.inwclist(wadio.entries[i].name, self.tail):
                        self[name][wadio.entries[i].name] = \
                            self.lumptype(wadio.read(i))
                        wadio.entries[i].been_read = True
                        i += 1
            if not added:
                i += 1

    def save_wadio(self, wadio):
        """Save to a WadIO object."""
        for h in self:
            hs = self[h]
            wadio.insert(h, "")
            for t in self.tail:
                if t in hs:
                    wadio.insert(t, hs[t].data)


class NameGroup(LumpGroup):
    """Group for lumps recognized by special names"""

    def __init2__(self):
        self.names = self.config

    def load_wadio(self, wadio):
        """Load all matching lumps that have not already
        been flagged as read from the given WadIO object."""

        for i, entry in ((i, e)
                for (i, e) in enumerate(wadio.entries)
                if not e.been_read and util.inwclist(e.name, self.names)):
            self[entry.name] = self.lumptype(wadio.read(i))
            entry.been_read = True

class TxdefGroup(NameGroup):
    """Group for texture definition lumps"""
    def __init2__(self):
        self.names = ['TEXTURE?', 'PNAMES']
    def __add__(self, other):
        from omg import txdef
        a = txdef.Textures()
        a.from_lumps(self)
        a.from_lumps(other)
        return a.to_lumps()
    def save_wadio(self, wadio):
        NameGroup.save_wadio(self, wadio)


#---------------------------------------------------------------------
#
# This defines the default structure for WAD files.
#

# First some lists...
_mapheaders = ['E?M?', 'MAP??*']
_maptail    = ['THINGS',   'LINEDEFS', 'SIDEDEFS', # Must be in order
               'VERTEXES', 'SEGS',     'SSECTORS',
               'NODES',    'SECTORS',  'REJECT',
               'BLOCKMAP', 'BEHAVIOR', 'SCRIPT*']
_glmapheaders = ['GL_E?M?', 'GL_MAP??']
_glmaptail    = ['GL_VERT', 'GL_SEGS', 'GL_SSECT', 'GL_NODES']
_graphics     = ['TITLEPIC', 'CWILV*', 'WI*', 'M_*',
                 'INTERPIC', 'BRDR*',  'PFUB?', 'ST*',
                 'VICTORY2', 'CREDIT', 'END?',  'WI*',
                 'BOSSBACK', 'ENDPIC', 'HELP',  'BOX??',
                 'AMMNUM?',  'HELP1',  'DIG*']

# The default structure object.
# Must be in order: markers first, ['*'] name group last
defstruct = [
    [MarkerGroup, 'sprites',   lump.Graphic, 'S'],
    [MarkerGroup, 'patches',   lump.Graphic, 'P'],
    [MarkerGroup, 'flats',     lump.Flat,    'F'],
    [MarkerGroup, 'colormaps', lump.Lump,    'C'],
    [MarkerGroup, 'ztextures', lump.Graphic, 'TX'],
    [HeaderGroup, 'maps',   lump.Lump, [_mapheaders, _maptail]],
    [HeaderGroup, 'glmaps', lump.Lump, [_glmapheaders, _glmaptail]],
    [NameGroup,   'music',    lump.Music, ['D_*']],
    [NameGroup,   'sounds',   lump.Sound, ['DS*', 'DP*']],
    [TxdefGroup,  'txdefs',   lump.Lump,  ['TEXTURE?', 'PNAMES']],
    [NameGroup,   'graphics', lump.Graphic, _graphics],
    [NameGroup,   'data',     lump.Lump,  ['*']]
]

write_order = ['data', 'colormaps', 'maps', 'glmaps', 'txdefs',
    'sounds', 'music', 'graphics', 'sprites', 'patches', 'flats',
    'ztextures']

class WAD:
    """A memory-resident, abstract representation of a WAD file. Lumps
    are stored in subsections of the WAD. Loading/saving and handling
    the sections follows the structure specification.

    Initialization:
    new = WAD([from_file, structure])

    Source may be a string representing a path to a file to load from.
    By default, an empty WAD is created.

    Structure may be used to specify a custom lump
    categorization/loading configuration.

    Member data:
        .structure     Structure definition.
        .palette       Palette (not implemented yet)
        .sprites, etc  Sections containing lumps, as specified by
                       the structure definition"""

    def __init__(self, from_file=None, structure=defstruct):
        """Create a new WAD. The optional `source` argument may be a
        string specifying a path to a file or a WadIO object.
        If omitted, an empty WAD is created. A WADStructure object
        may be passed as the `structure` argument to apply a custom
        section structure. By default, the structure specified in the
        defdata module is used."""
        self.__category = 'root'
        self.palette = palette.default
        self.structure = structure
        self.groups = []
        for group_def in self.structure:
            instance = group_def[0](*tuple(group_def[1:]))
            self.__dict__[group_def[1]] = instance
            self.groups.append(instance)
        if from_file:
            self.from_file(from_file)

    def from_file(self, source):
        """Load contents from a file. `source` may be a string
        specifying a path to a file or a WadIO object."""
        if isinstance(source, WadIO):
            w = source
        elif isinstance(source, str):
            assert os.path.exists(source)
            w = WadIO(source)
        else:
            raise TypeError, "Expected WadIO or file path string"
        for group in self.groups:
            group.load_wadio(w)

    def to_file(self, filename):
        """Save contents to a WAD file. Caution: if a file with the given name
        already exists, it will be overwritten. However, the existing file will
        be kept as <filename>.tmp until the operation has finished, to stay safe
        in case of failure."""
        use_backup = os.path.exists(filename)
        tmpfilename = filename + ".tmp"
        if use_backup:
            if os.path.exists(tmpfilename):
                os.remove(tmpfilename)
            os.rename(filename, tmpfilename)
        w = WadIO(filename)
        for group in write_order:
            self.__dict__[group].save_wadio(w)
        w.save()
        if use_backup:
            os.remove(tmpfilename)

    def __add__(self, other):
        assert isinstance(other, WAD)
        w = WAD(structure=self.structure)
        for group_def in self.structure:
            name = group_def[1]
            w.__dict__[name] = self.__dict__[name] + other.__dict__[name]
        return w

    def copy(self):
        return util.deepcopy(self)
