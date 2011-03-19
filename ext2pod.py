#! /usr/bin/python
# -*- coding: utf-8 -*-

import sys, re, os
import pyparsing
from HTMLParser import HTMLParser
from collections import defaultdict

debug = False

class Node(object):
    "An HTML tag that knows how to render itself into pod"

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = attrs
        self.children = []

    def add(self, child):
        self.children.append(child)

    def __repr__(self):
        return '%s(%s)' % (self.tag, ', '.join(map(repr, self.children)))

    def pod(self, plain=False):
        def render_content(plain):
            return ''.join([child if isinstance(child, basestring) else child.pod(plain=plain) for child in self.children])

        if self.tag == 'pre':
            content = render_content(True)
            return '\n\n\t' + content.replace('\n', '\n\t')

        content = render_content(plain)

        if plain:
            return content

        if self.tag in ('root', 'div', 'u', 'em'):
            return content
        elif self.tag == 'a':
            print >>sys.stderr, '<A> attrs=%r' % self.attrs
            return content
        elif self.tag == 'p':
            return content + '\n\n'
        elif self.tag in ('code', 'tt'):
            return 'C<%s>' % content
        elif self.tag == 'b':
            return 'B<%s>' % content
        elif self.tag in ('i', 'link'):
            return 'I<%s>' % content
        elif self.tag == 'ul':
            return '\n\n=over\n' + content + '\n\n=back\n'
        elif self.tag == 'li':
            return '\n=item ' + content
        elif self.tag == 'br':
            return ''
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
        node = Node(tag, attrs)
        self.nodes[-1].add(node)
        self.nodes.append(node)

    def handle_endtag(self, tag):
        if self.nodes[-1].tag == tag:
            self.nodes.pop()
        else:
            print >>sys.stderr, 'Unbalanced close tag %r (expecting %r)' % (tag, self.nodes[-1].tag)

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
            try:
                node.add(link.split()[-1].replace('#', '')) # FIXME replace only leading #
            except IndexError:
                print >>sys.stderr, 'Malformed link %r' % link
            else:
                cur.add(node)

            start = data.find('{@link', end)

        cur.add(data[end:])

class Text(object):
    def __init__(self, s):
        if isinstance(s, list):
            s = '\n'.join(s)

        self.parse(s)

    def parse(self, s):
        nodes = HTMLNodes()
        nodes.feed(s)
        self.text = nodes.root()

    def __str__(self):
        return self.text.pod()

    def __repr__(self):
        return 'Text(' + repr(self.text) + ')'

def render_params_details(params):
    result = []
    for param in params:
        result.append('=item ' + param.pod())
    return '\n\n'.join(result)

def render_params_summary(params):
    result = []
    for param in params:
        result.append('%s: %s' % (param.name, param.type))
    return ', '.join(result)

class DocNode(object):
    def __init__(self, name):
        self._name = name
        self.children = defaultdict(list)

    def append(self, node):
        self.children[type(node)].append(node)

    def get_generic_list(self, name):
        return [g for g in self.children[Generic] if g._name == name]

    def get_generic(self, name):
        gs = self.get_generic_list(name)

        assert len(gs) <= 1

        try:
            return gs[0].text
        except IndexError:
            return None

    def dump(self, indent=0):
        print ' '*indent, self._name, getattr(self, 'name', '')
        for name, items in self.children.items():
            for item in items:
                item.dump(indent=indent+2)

class Generic(DocNode):
    def __init__(self, name, lines):
        super(Generic, self).__init__(name)

        self.text = Text(lines)

    def pod(self):
        return str(self.text)

class Class(DocNode):
    def __init__(self, name, lines):
        super(Class, self).__init__(name)

        self.name = lines[0]
        self.text = Text(lines[1:])

    def __repr__(self):
        return 'Class(' + repr(self.name) + ')'

    def pod(self):
        self.extends = self.get_generic('extends')
        self.xtype = self.get_generic('xtype')
        return """\
B<%(name)s> %(extends)s %(xtype)s

=over 4

%(text)s

=back

""" % self.__dict__

class Cfg(DocNode):
    re_ = re.compile('\s*({[a-zA-Z./]+})?\s*(\w+)\s*')
    default_re = re.compile('defaults to\s+(\S+)')

    def __init__(self, name, lines):
        super(Cfg, self).__init__(name)

        cfg = lines[0]

        self.name = 'FIXME'
        self.type = 'FIXME'
        self.default = 'FIXME'
        self.text = 'FIXME'

        m = Cfg.re_.match(cfg)
        if m is None:
            print >>sys.stderr, 'Malformed cfg %r' % cfg
            return

        start, end = m.span()

        self.type = m.group(1).lstrip('{').rstrip('}') if m.group(1) else '_'
        self.name = m.group(2)
        lines.insert(0, cfg[end:])
        s = '\n'.join(lines)
        self.text = Text(s)

        m = Cfg.default_re.search(s)
        if m:
            default = m.group(1)
            default = default.rstrip(').')
            self.default = Text(default)
        else:
            self.default = ''

    def __repr__(self):
        return 'Cfg(%s)' % ', '.join(['%s=%r' % (name, getattr(self, name)) for name in ['name', 'type', 'default', 'text']])

    def pod(self):
        return """\
B<%(name)s> %(type)s %(default)s

=over 4

%(text)s

=back

""" % self.__dict__

class Param(DocNode):
    # {type} name text
    re_ = re.compile('({[^}]+})?\s*(\w+)\s*(.*)')
    def __init__(self, name, lines):
        super(Param, self).__init__(name)
        c = lines[0]

        m = Param.re_.match(c)
        if m:
            self.type = m.group(1)
            if self.type:
                self.type = self.type.lstrip('{').rstrip('}')
            self.name = m.group(2)
            lines.insert(0, m.group(3))
            self.text = Text(lines)
        else:
            self.name = '???'
            self.type = '???'
            self.text = c
            print >>sys.stderr, 'malformed Param', c

    def __repr__(self):
        return 'Param(' + repr(self.name) + ')'

    def pod(self):
        return "%s\t%s" % (self.name, self.text)

class Method(DocNode):
    def __init__(self, name, lines):
        super(Method, self).__init__(name)

        self.name = lines[0]

        self.text = Text(lines[1:])

    def __repr__(self):
        return 'Method(' + repr(self.name) + ')'

    def pod(self):
        params = self.children[Param]
        self.params_summary = render_params_summary(params)
        self.params_details = render_params_details(params)
        self.return_ = self.get_generic('return')

        return """\
B<%(name)s>(%(params_summary)s) -> %(return_)s

=over 4

=over 2

%(params_details)s

=back

%(text)s

=back

""" % self.__dict__

class Event(DocNode):
    def __init__(self, name, lines):
        super(Event, self).__init__(name)

        self.name = lines[0]
        self.text = Text(lines[1:])

    def __repr__(self):
        return 'Event(' + repr(self.name) + ')'

    def pod(self):
        params = self.children[Param]
        self.params_summary = render_params_summary(params)
        self.params_details = render_params_details(params)

        return """\
B<%(name)s>(%(params_summary)s)

=over 4

=over 2

%(params_details)s

=back

%(text)s

=back

""" % self.__dict__

class Property(DocNode):
    def __init__(self, name, lines):
        super(Property, self).__init__(name)

        self.name = lines[0]
        self.text = Text(lines[1:])

    def __repr__(self):
        return 'Property(' + repr(self.name) + ')'

    def pod(self):
        self.type = self.get_generic('type')
        return """\
B<%(name)s> %(type)s

=over 4

%(text)s

=back

""" % self.__dict__

at_options = defaultdict(lambda: (2, False, Generic))
at_options['class'] = 0, True, Class
at_options['event'] = 1, True, Event
at_options['cfg'] = 1, True, Cfg
at_options['property'] = 1, True, Property
at_options['method'] = 1, True, Method
at_options['param'] = 2, True, Param

class At(object):
    def __init__(self, name, line=None):
        self.name = name
        self.lines = []
        if line:
            self.lines.append(line)

    def append(self, line):
        self.lines.append(line)

    def __repr__(self):
        if len(self.lines) == 0:
            return '%s' % self.name
        elif len(self.lines) == 1:
            return '%s: [%r]' % (self.name, self.lines[0])
        else:
            return '%s: [%r, ...]' % (self.name, self.lines[0])

star_re = re.compile('^\s*\*\s*', re.MULTILINE)
function_re = re.compile('\s*(\w+)\s*:\s*function')

def parse_comment(c, s, end):
    def remove_stars(c):
        # remove /**, *s and */
        c = re.sub('^/\*\*\s*', '', c)
        c = re.sub('\s*\*/$', '', c)
        return star_re.sub('', c)

    def match(s, start, re_):
        m = re_.match(s, start)
        if m:
            return m.group(1)
        else:
            return None

    def split(line):
        at_end = line.find(' ') # FIXME any space
        if at_end == -1:
            return line[1:], ''
        else:
            return line[1:at_end], line[at_end+1:]

    ats = []

    cursor = None # where to append lines not starting with @
    for line in remove_stars(c).split('\n'):
        if line.startswith('@'):
            at, line = split(line)
            at = At(at, line)
            ats.append(at)
            _, multiline, _ = at_options[at.name]
            if multiline:
                cursor = at
        else:
            if not cursor:
                cursor = At('_') # dummy at to collect lines if no real at was seen yet
                ats.insert(0, cursor)
            cursor.append(line)

    if not set([at.name for at in ats]) & set(['cfg', 'class', 'property']):
        # collect the js identifier following this block of comments
        name = match(s, end, function_re)
        if name:
            ats.append(At('method', name))
        else:
            print >>sys.stderr, 'Comment doesn\'t contain any leader'

    # merge the lines of the leader into the dummy element
    if ats[0].name == '_':
        for leader_index, leader in enumerate(ats):
            if leader.name in ('cfg', 'class', 'property', 'method'):
                ats[0].name = leader.name
                ats[0].lines.insert(0, leader.lines[0])
                ats[0].lines.extend(leader.lines[1:]) # does this happen?

                ats[leader_index] = None

    return filter(None, ats)

class Document(object):
    Sections = [
        (Generic, 'DEBUGGING'),
        (Class, 'DESCRIPTION'),
        (Cfg, 'CONFIGURATION'),
        (Property, 'PROPERTIES'),
        (Method, 'METHODS'),
        (Event, 'EVENTS'),
    ]

    def __init__(self, s):
        self.classes = []
        self.parse(s)

    def parse(self, s):
        ats = []
        for p in pyparsing.cStyleComment('lalala').scanString(s):
            c = p[0][0]
            if c.startswith('/**'):
                ats.extend(parse_comment(c, s, p[2]))

        if debug:
            print 'LIST DUMP'
            import pprint
            pprint.pprint(ats)

        # build tree starting from flat ats
        self.classes = []
        cursor = self.classes # where to append nodes
        for at in ats:
            level, _, class_ = at_options[at.name]
            node = class_(at.name, at.lines)

            if level == 0:
                self.classes.append(node)
                cursor = node
            elif level == 1:
                self.classes[-1].append(node)
                cursor = node
            else:
                cursor.append(node)

        if debug:
            print 'TREE DUMP'
            for class_ in self.classes:
                class_.dump()

    def pod(self, class_):
        s = """\
=pod

=encoding utf8

"""

        s += "\n\n=head1 DESCRIPTION\n\n"
        s += class_.pod()

        for section_class, section_header in self.Sections:
            if class_.children[section_class]:
                s += "\n\n=head1 %s\n\n" % section_header

                for item in sorted(class_.children[section_class], key=lambda i: getattr(i, 'name', '')):
                    if hasattr(item, 'pod'):
                        s += item.pod()
                    else:
                        print >>sys.stderr, repr(item)

        s += "=cut"

        return s

    def save_pods(self):
        def filename(class_):
            # remove leading namespaces
            # return class_.name.rsplit('.', 1)[-1]
            # remove leading namespace
            try:
                return class_.name.split('.', 1)[1]
            except IndexError:
                return class_.name

        for class_ in self.classes:
            with open('%s.pod' % filename(class_), 'w') as out:
                print >>out, self.pod(class_)

if sys.argv[1] == '-d':
    debug = True
    filename = sys.argv[2]
else:
    filename = sys.argv[1]

if os.path.basename(filename).startswith('ext-lang-'):
    print 'Skipping translation file', os.path.basename(filename)
    sys.exit(0)

Document(open(filename).read()).save_pods()
