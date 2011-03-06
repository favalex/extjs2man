#! /usr/bin/python

import sys, re
import pyparsing
from HTMLParser import HTMLParser

class Node(object):
    def __init__(self, tag):
        self.tag = tag
        self.children = []

    def add(self, child):
        self.children.append(child)

    def __repr__(self):
        return '%s(%s)' % (self.tag, ', '.join(map(repr, self.children)))

class HTMLNodes(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)

        self.nodes = [Node('root')]

    def root(self):
        return self.nodes[0]

    def handle_starttag(self, tag, attrs):
        node = Node(tag)
        self.nodes[-1].add(node)
        self.nodes.append(node)

    def handle_endtag(self, tag):
        self.nodes.pop()

    def handle_data(self, data):
        self.nodes[-1].add(data)

def extract(marker, cs, arity=1):
    result = []
    dels = []

    for i, c in enumerate(cs):
        if c.startswith(marker):
            result.append(c[len(marker):].strip())
            dels.append(i)

    for i in reversed(dels):
        del cs[i]

    if arity == 1:
        if len(result) == 1:
            return result[0]
        else:
            raise ValueError('expected arity 1, found %d items' % len(result))
    elif arity == '?':
        if len(result) == 1:
            return result[0]
        elif len(result) == 0:
            return None
        else:
            raise ValueError('expected arity ?, found %d items' % len(result))
    else:
        return result

def warn_if_markers(cs):
    for c in cs:
        if c.startswith('@'):
            print >>sys.stderr, 'warn: unprocessed marker', c

class Text(object):
    def __init__(self, s):
        self.parse(s)

    def parse(self, s):
        nodes = HTMLNodes()
        nodes.feed(s)
        self.text = nodes.root()

    def __str__(self):
        return repr(self.text) # FIXME

    def __repr__(self):
        return 'Text(' + repr(self.text) + ')'

class Comment(object):
    @classmethod
    def marker(cls):
        return '@' + cls.__name__.lower()

    def __init__(self, cs):
        self.cs = cs

    def __str__(self):
        return '----\n' + ('\n'.join(self.cs)) + '----\n'

    def __repr__(self):
        return 'Comment(' + repr(self.cs[0]) + ')'

class Unknown(Comment):
    pass

class Class(Comment):
    # name, extends, xtype, constructor
    def __init__(self, cs):
        self.name = extract('@class', cs)
        self.extends = extract('@extends', cs, '?')
        self.constructor = extract('@constructor', cs, '?')
        self.xtype = extract('@xtype', cs, '?')

        warn_if_markers(cs)

        self.text = '\n'.join(cs)

    def __str__(self):
        return 'class %s(%s)' % (self.name, self.extends)

    def __repr__(self):
        return 'Class(' + repr(self.name) + ')'

class Cfg(Comment):
    re_ = re.compile('@cfg\s+{([a-zA-Z./]+)}\s+(\w+)\s+')
    default_re = re.compile('defaults to\s+(\S+)')

    def __init__(self, cs):
        self.parse('\n'.join(cs))

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
        return "%s %s %s" % (self.name, self.type, self.default)

    def __repr__(self):
        return 'Cfg(%s)' % ', '.join(['%s=%r' % (name, getattr(self, name)) for name in ['name', 'type', 'default', 'text']])

    def pod(self):
        return """\
I<%(name)s> %(type)s %(default)s

=over 4

%(text)s

=back

""" % self.__dict__

class Param(object):
    # {type} name text
    re_ = re.compile('{([a-zA-Z0-9._/]+)}\s+(\w+)\s*(.*)')
    def __init__(self, c):
        m = Param.re_.match(c)
        if m:
            self.type = m.group(1)
            self.name = m.group(2)
            self.text = m.group(3)
        else:
            print >>sys.stderr, 'malformed Param', c

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Param(' + repr(self.name) + ')'

class Method(Comment):
    # name, params, return, text
    def __init__(self, cs):
        self.name = extract('@method', cs)
        self.params = map(Param, extract('@param', cs, '*'))
        self.return_ = extract('@return', cs, '?')

        warn_if_markers(cs)

        self.text = '\n'.join(cs)

    def __str__(self):
        return '@method %s(%s) -> %s' % (self.name, ', '.join(map(str, self.params)), self.return_)

    def __repr__(self):
        return 'Method(' + repr(self.name) + ')'

class Event(Comment):
    # name, params, text
    def __init__(self, cs):
        self.name = extract('@event', cs)
        self.params = map(Param, extract('@param', cs, '*'))

        warn_if_markers(cs)

        self.text = '\n'.join(cs)

    def __str__(self):
        return 'event %s(%s)' % (self.name, ', '.join(map(str, self.params)))

    def __repr__(self):
        return 'Event(' + repr(self.name) + ')'

class Property(Comment):
    # name, type, text
    def __init__(self, cs):
        self.name = extract('@property', cs)
        self.type = extract('@type', cs, 1)

        warn_if_markers(cs)

        self.text = '\n'.join(cs)

    def __str__(self):
        return 'property %s %s' % (self.name, self.type)

    def __repr__(self):
        return 'Property(' + repr(self.name) + ')'

CommentTypes = [Class, Cfg, Event, Method, Property]

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
            # remove /**, *s and */
            c = re.sub('^/\*\*\s*', '', c)
            c = re.sub('\s*\*/$', '', c)
            c = star_re.sub('', c)

            cs = c.split('\n')
            c = cs[0]

            # normalize first line into '@xxx' form
            if c[0] != '@':
                m = property_re.search(c)
                if m:
                    # move @property at the beginning of the line
                    pstart, pend = m.span()
                    c = c[pstart:] + c[:pstart]
                else:
                    # methods are implicit, make them explicit
                    m = identifier_re.match(s, end)
                    if m:
                        c = '@method ' + m.group(1)
                        cs.insert(0, c)
                    else:
                        # TODO try backwards
                        pass

            result = Unknown(cs)
            for C in CommentTypes:
                if c.startswith(C.marker()):
                    result = C(cs)
                    break

            yield result

for d in doc(s):
    try:
        print d.pod()
    except AttributeError:
        print >>sys.stderr, repr(d)
