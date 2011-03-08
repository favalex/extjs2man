#! /usr/bin/python
# -*- coding: utf-8 -*-

import sys, re
import pyparsing
from HTMLParser import HTMLParser
from collections import defaultdict

class Node(object):
    def __init__(self, tag):
        self.tag = tag
        self.children = []

    def add(self, child):
        self.children.append(child)

    def __repr__(self):
        return '%s(%s)' % (self.tag, ', '.join(map(repr, self.children)))

    def __unicode__(self):
        content =  ''.join([unicode(child) for child in self.children])

        if self.tag in ('root', 'div'):
            return content
        elif self.tag == 'p':
            return content + '\n\n'
        elif self.tag in ('code', 'tt'):
            return 'C<%s>' % content
        elif self.tag == 'b':
            return 'B<%s>' % content
        elif self.tag in ('i', 'link'):
            return 'I<%s>' % content
        elif self.tag == 'pre':
            return '\t' + content.replace('\n', '\n\t')
        elif self.tag == 'ul':
            return '\n=over\n' + content + '\n=back\n'
        elif self.tag == 'li':
            return '\n=item ' + content
        else:
            print >>sys.stderr, "Don't know how to render tag %r" % self.tag
            return content

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
        cur = self.nodes[-1]

        end = 0
        start = data.find('{@link')
        while start > -1 and start < len(data):
            cur.add(data[end:start])
            start += 7

            end = data.find('}', start)
            if end == -1:
                print >>sys.stderr, 'warn: missing closing } after {@link'
                end = len(data)

            end += 1
            node = Node('link')
            link = data[start:end-1]
            node.add(link.split()[-1].replace('#', '')) # FIXME replace only leading #
            cur.add(node)

            start = data.find('{@link', end)

        cur.add(data[end:])

def extract(marker, ats, arity=1):
    result = ats.pop(marker, [])

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

def warn_if_markers(section, ats):
    if ats:
        print >>sys.stderr, 'warn: unprocessed markers', ats.keys(), 'in section', section

class Text(object):
    def __init__(self, s):
        self.parse(s)

    def parse(self, s):
        nodes = HTMLNodes()
        nodes.feed(s)
        self.text = nodes.root()

    def __str__(self):
        return unicode(self.text) # FIXME

    def __repr__(self):
        return 'Text(' + repr(self.text) + ')'

class Comment(object):
    @classmethod
    def marker(cls):
        return cls.__name__.lower()

    def __init__(self, cs, ats):
        self.cs = cs

    def __str__(self):
        return '----\n' + ('\n'.join(self.cs)) + '----\n'

    def __repr__(self):
        return 'Comment(' + repr(self.cs[0]) + ')'

class Unknown(Comment):
    pass

class Class(Comment):
    # name, extends, xtype, constructor
    def __init__(self, cs, ats):
        self.name = extract('class', ats)
        self.extends = extract('extends', ats, '?')
        self.constructor = extract('constructor', ats, '?')
        self.xtype = extract('xtype', ats, '?')

        warn_if_markers('Class', ats)

        self.text = Text('\n'.join(cs))

    def __str__(self):
        return 'class %s(%s)' % (self.name, self.extends)

    def __repr__(self):
        return 'Class(' + repr(self.name) + ')'

    def pod(self):
        # FIXME constructor
        return """\
B<%(name)s> %(extends)s %(xtype)s

=over 4

%(text)s

=back

""" % self.__dict__

class Cfg(Comment):
    re_ = re.compile('\s*{([a-zA-Z./]+)}\s+(\w+)\s*')
    default_re = re.compile('defaults to\s+(\S+)')

    def __init__(self, cs, ats):
        cfg = extract('cfg', ats)

        m = Cfg.re_.match(cfg)

        start, end = m.span()

        self.type = m.group(1)
        self.name = m.group(2)
        cs.insert(0, cfg[end:])
        s = '\n'.join(cs)
        self.text = Text(s)

        m = Cfg.default_re.search(s)
        if m:
            self.default = m.group(1) # FIXME Text
        else:
            self.default = ''

    def __str__(self):
        return "%s %s %s" % (self.name, self.type, self.default)

    def __repr__(self):
        return 'Cfg(%s)' % ', '.join(['%s=%r' % (name, getattr(self, name)) for name in ['name', 'type', 'default', 'text']])

    def pod(self):
        return """\
B<%(name)s> %(type)s %(default)s

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
    def __init__(self, cs, ats):
        self.name = extract('method', ats)
        self.params = map(Param, extract('param', ats, '*'))
        self.return_ = extract('return', ats, '?')

        warn_if_markers('Method', ats)

        self.text = Text('\n'.join(cs))

    def __str__(self):
        return '@method %s(%s) -> %s' % (self.name, ', '.join(map(str, self.params)), self.return_)

    def __repr__(self):
        return 'Method(' + repr(self.name) + ')'

    def pod(self):
        self.params_summary = ', '.join([param.name for param in self.params])

        return """\
B<%(name)s>(%(params_summary)s) -> %(return_)s

=over 4

%(text)s

=back

""" % self.__dict__

class Event(Comment):
    # name, params, text
    def __init__(self, cs, ats):
        self.name = extract('event', ats)
        self.params = map(Param, extract('param', ats, '*'))

        warn_if_markers('Event', ats)

        self.text = Text('\n'.join(cs))

    def __str__(self):
        return 'event %s(%s)' % (self.name, ', '.join(map(str, self.params)))

    def __repr__(self):
        return 'Event(' + repr(self.name) + ')'

    def pod(self):
        self.params_summary = ', '.join([param.name for param in self.params])

        return """\
B<%(name)s> %(params_summary)s

=over 4

%(text)s

=back

""" % self.__dict__

class Property(Comment):
    # name, type, text
    def __init__(self, cs, ats):
        self.name = extract('property', ats)
        self.type = extract('type', ats, 1)

        warn_if_markers('Property', ats)

        self.text = Text('\n'.join(cs))

    def __str__(self):
        return 'property %s %s' % (self.name, self.type)

    def __repr__(self):
        return 'Property(' + repr(self.name) + ')'

    def pod(self):
        return """\
B<%(name)s> %(type)s

=over 4

%(text)s

=back

""" % self.__dict__

class Document(object):
    Sections = [
        (Class, 'classes', 'DESCRIPTION'),
        (Cfg, 'cfgs', 'CONFIGURATION'),
        (Property, 'properties', 'PROPERTIES'),
        (Method, 'methods', 'METHODS'),
        (Event, 'events', 'EVENTS'),
    ]

    def __init__(self, s):
        self.classes = []
        self.cfgs = []
        self.events = []
        self.methods = []
        self.properties = []
        self.unknown = []

        self.parse(s)

    def parse(self, s):
        star_re = re.compile('^\s*\*\s*', re.MULTILINE)

        def remove_stars(c):
            # remove /**, *s and */
            c = re.sub('^/\*\*\s*', '', c)
            c = re.sub('\s*\*/$', '', c)
            return star_re.sub('', c)

        for p in pyparsing.cStyleComment('lalala').scanString(s):
            c = p[0][0]
            if c.startswith('/**'):
                lines = []
                ats = defaultdict(list)

                for line in remove_stars(c).split('\n'):
                    if line.startswith('@'):
                        at_end = line.find(' ') # FIXME any space
                        ats[line[1:at_end]].append(line[at_end+1:])
                    else:
                        lines.append(line)

                found = False
                for C, attname, _ in self.Sections:
                    if C.marker() in ats:
                        found = True
                        getattr(self, attname).append(C(lines, ats))
                        break

                if not found:
                    ats['method'] = 'xxx'
                    self.unknown.append(Method(lines, ats))

    def pod(self):
        s = """\
=pod
=encoding utf8
"""

        for _, attname, section_header in self.Sections:
            if getattr(self, attname):
                s += "=head2 %s\n\n" % section_header

                for item in sorted(getattr(self, attname), key=lambda i: i.name):
                    try:
                        s += item.pod()
                    except AttributeError:
                        print >>sys.stderr, repr(item)

        s += "=cut"

        return s

in_file_name = sys.argv[1]

with open(in_file_name) as f:
    s = f.read()

print Document(s).pod()
