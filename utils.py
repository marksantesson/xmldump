
import datetime
import functools
import logging
import os
import re
import tempfile
import time
from   xml.etree import ElementTree as ET


class EnableAsDecorator(object):
    def __call__(self, f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            with self:
                return f(*args, **kwargs)
        return decorated


class TemporaryFileContext(EnableAsDecorator):
    '''This creates a context that will make a temporary file
    that will be automatically deleted when the context is exited.
    It can be used as a decorator. The filename will be generated
    by tempfile if not given; the name selected is available
    after the context is entered from teh fileName() method.
    The contents of the file must be passed to the constructor.
    '''

    def __init__(self, contents, name=None):
        self._contents = contents
        self._name     = name

    def __enter__(self):
        if self._name is None:
            file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
            self._tempname = file.name
        else:
            file = open(self._name, 'wb')
        file.write(self._contents)
        file.close()
        return self

    def __exit__(self, x, y, z):
        if hasattr(self, '_tempname'):
            os.unlink(self._tempname)
            del self._tempname

    def fileName(self):
        return self._name or self._tempname


class LoggingFilterContext(logging.Filter, EnableAsDecorator):
    def __init__(self, pass_fn):
        self._pass_fn = pass_fn

    @classmethod
    def annotate(cls, pass_fn):
        def wrapper(f):
            f.logging_filter = cls(pass_fn)
            return f
        return wrapper

    @classmethod
    def annotate_regex(cls, pass_re):
        return cls.annotate( lambda rec: re.match( pass_re, rec.getMessage() ) )

    @classmethod
    def annotate_not_regex(cls, fail_re):
        return cls.annotate( lambda rec: not re.match( fail_re
                                                     , rec.getMessage() ) )

    def filter(self, record):
        return self._pass_fn(record)

    def __enter__(self):
        logger = logging.getLogger()
        logger.addFilter(self)
        return self

    def __exit__(self, x, y, z):
        logger = logging.getLogger()
        logger.removeFilter(self)


def indent_xml(xml, collapse_leaves=True):
    from xml.dom.minidom import parseString
    doc = parseString( xml if isinstance(xml,basestring) else ET.tostring(xml) )
    xml = doc.toprettyxml('  ')
    if collapse_leaves:
        lines = xml.split('\n')
        i = 2
        regex = re.compile('^(\s*)')
        while i < len(lines):
            wslen = [ len(regex.match(lines[i-ii]).group(1)) for ii in (2,1,0) ]
            if wslen[0]==wslen[2] and wslen[1] > wslen[0]:
                lines[i-2] = lines[i-2] + lines[i-1].strip() + lines[i].strip()
                del lines[i-1:i+1]
                i -= 2
            i += 1
        xml = '\n'.join(lines)
    return xml

