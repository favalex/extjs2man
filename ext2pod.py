#! /usr/bin/python

import sys, re
import pyparsing

class Text(object):
    def __init__(self, s):
        self.parse(s)

    def parse(self, s):
        self.text = s

    def __str__(self):
        return self.text

class Cfg(object):
    re_ = re.compile('@cfg\s+{([a-zA-Z./]+)}\s+(\w+)\s+')
    default_re = re.compile('defaults to\s+(\S+)')

    def __init__(self, s):
        self.parse(s)

    def parse(self, s):
        m = Cfg.re_.match(s)

        start, end = m.span()

        self.type = m.group(1)
        self.name = m.group(2)
        self.text = Text(s[end:])

        m = Cfg.default_re.search(s)
        if m:
            self.default = m.group(1)
        else:
            self.default = ''

    def __str__(self):
        return "%s %s" % (self.name, self.type)

    def pod(self):
        return """\
I<%(name)s> %(type)s %(default)s

=over 4

%(text)s

=back

""" % self.__dict__

class Method(object):
    # name, params, returns, text
    pass

class Event(object):
    # name, params, text
    pass

class Property(object):
    # name, type, text
    pass

in_file_name = sys.argv[1]

with open(in_file_name) as f:
    s = f.read()

def doc(s):
    star_re = re.compile('^\s*\*\s*', re.MULTILINE)
    identifier_re = re.compile('\s*(\w+)')
    property_re = re.compile('@property\s+\w+\s*$')

    for p in pyparsing.cStyleComment('lalala').scanString(s):
        c = p[0][0]
        start = p[1]
        end = p[2]
        if c.startswith('/**'):
            c = re.sub('^/\*\*\s*', '', c)
            c = re.sub('\*/$', '', c)
            c = star_re.sub('', c)
            c = c.replace('\n', ' ')
            if c[0] != '@':
                m = property_re.search(c)
                if m:
                    pstart, pend = m.span()
                    c = c[pstart:] + c[:pstart]
                else:
                    m = identifier_re.match(s, end)
                    if m:
                        c = '@method ' + m.group(1) + ' ' + c
            if c.startswith('@cfg'):
                c = Cfg(c)

            yield c

for d in doc(s):
    try:
        print d.pod()
    except AttributeError:
        pass
