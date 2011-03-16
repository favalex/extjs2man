#! /usr/bin/python
# -*- coding: utf-8 -*-

import sys, re
import pyparsing
from HTMLParser import HTMLParser
from collections import defaultdict

class Node(object):
    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = attrs
        self.children = []

    def add(self, child):
        self.children.append(child)

    def __repr__(self):
        return '%s(%s)' % (self.tag, ', '.join(map(repr, self.children)))

    def render(self, plain=False):
        def render_content(plain):
            return ''.join([child if isinstance(child, basestring) else child.render(plain=plain) for child in self.children])

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
        self.parse(s)

    def parse(self, s):
        nodes = HTMLNodes()
        nodes.feed(s)
        self.text = nodes.root()

    def __str__(self):
        return self.text.render()

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

class Dummy(object):
    def __init__(self, lines):
        self.name = 'dummy'
        self.children = defaultdict(list)

    def __repr__(self):
        return 'Dummy(' + repr(self.name) + ')'

class Class(object):
    def __init__(self, lines):
        self.name = lines[0]
        self.text = Text('\n'.join(lines[1:]))
        self.children = defaultdict(list)

    def __repr__(self):
        return 'Class(' + repr(self.name) + ')'

    def append_child(self, child):
        Level1 = {
            'extends': Dummy,
            'cfg': Cfg,
            'event': Event,
            'method': Method,
            'property': Property,
            'constructor': Dummy,
        }

        if child.name in Level1.keys():
            self.latest_child = child
            self.children[child.name].append(Level1[child.name](child.lines))
        else:
            try:
                self.latest_child.append(child)
            except IndexError:
                print 'orphan', child.name

    def pod(self):
        return """\
B<%(name)s> %(extends)s %(xtype)s

=over 4

%(text)s

=back

""" % self.__dict__

class Cfg(object):
    re_ = re.compile('\s*({[a-zA-Z./]+})?\s*(\w+)\s*')
    default_re = re.compile('defaults to\s+(\S+)')

    def __init__(self, lines):
        cfg = lines[0]

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

class Param(object):
    # {type} name text
    re_ = re.compile('({[^}]+})?\s*(\w+)\s*(.*)')
    def __init__(self, c):
        m = Param.re_.match(c)
        if m:
            self.type = m.group(1)
            if self.type:
                self.type = self.type.lstrip('{').rstrip('}')
            self.name = m.group(2)
            self.text = Text(m.group(3))
        else:
            self.name = '???'
            self.type = '???'
            self.text = c
            print >>sys.stderr, 'malformed Param', c

    def __repr__(self):
        return 'Param(' + repr(self.name) + ')'

    def pod(self):
        return "%s\t%s" % (self.name, self.text)

class Method(object):
    def __init__(self, lines):
        self.name = lines[0]

        self.text = Text('\n'.join(lines[1:]))

    def __repr__(self):
        return 'Method(' + repr(self.name) + ')'

    def pod(self):
        self.params_summary = 'FIXME' # render_params_summary(self.params)
        self.params_details = 'FIXME' # render_params_details(self.params)
        self.return_ = 'FIXME'

        return """\
B<%(name)s>(%(params_summary)s) -> %(return_)s

=over 4

=over 2

%(params_details)s

=back

%(text)s

=back

""" % self.__dict__

class Event(object):
    # name, params, text
    def __init__(self, lines):
        self.name = lines[0]

        self.text = Text('\n'.join(lines[1:]))

    def __repr__(self):
        return 'Event(' + repr(self.name) + ')'

    def pod(self):
        self.params_summary = 'FIXME' # render_params_summary(self.params)
        self.params_details = 'FIXME' # render_params_details(self.params)

        return """\
B<%(name)s>(%(params_summary)s)

=over 4

=over 2

%(params_details)s

=back

%(text)s

=back

""" % self.__dict__

class Property(object):
    def __init__(self, lines):
        self.name = lines[0]
        self.text = Text('\n'.join(lines[1:]))

    def __repr__(self):
        return 'Property(' + repr(self.name) + ')'

    def pod(self):
        self.type = 'FIXME'
        return """\
B<%(name)s> %(type)s

=over 4

%(text)s

=back

""" % self.__dict__

class Document(object):
    Sections = [
        (Class, 'class', 'DESCRIPTION'),
        (Cfg, 'cfg', 'CONFIGURATION'),
        (Property, 'property', 'PROPERTIES'),
        (Method, 'method', 'METHODS'),
        (Event, 'event', 'EVENTS'),
    ]

    def __init__(self, s):
        self.classes = []
        self.parse(s)

    def parse(self, s):
        star_re = re.compile('^\s*\*\s*', re.MULTILINE)
        function_re = re.compile('\s*(\w+)\s*:\s*function')
        identifier_re = re.compile('\s*(\w+)')

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

        class At(object):
            def __init__(self, name, line=None):
                self.name = name
                self.lines = []
                self.children = []
                if line:
                    self.lines.append(line)

            def append(self, line):
                self.lines.append(line)

            def append_child(self, child):
                if child.name not in ('extends', 'cfg', 'event', 'method', 'property', 'constructor'):
                    try:
                        self.children[-1].append(child)
                    except IndexError:
                        print 'orphan', child.name
                else:
                    self.children.append(child)

            def __repr__(self):
                if len(self.lines) == 0:
                    return '%s' % self.name
                elif len(self.lines) == 1:
                    return '%s: [%r]' % (self.name, self.lines[0])
                else:
                    return '%s: [%r, ...]' % (self.name, self.lines[0])

        def split(line):
            at_end = line.find(' ') # FIXME any space
            if at_end == -1:
                return line[1:], ''
            else:
                return line[1:at_end], line[at_end+1:]

        def rfind_by(xs, pred):
            for x in reversed(xs):
                if pred(x):
                    return x

        ats = []
        for p in pyparsing.cStyleComment('lalala').scanString(s):
            c = p[0][0]
            start_of_this_comment = len(ats)
            ats_in_this_comment = set()
            if c.startswith('/**'):
                for line in remove_stars(c).split('\n'):
                    if line.startswith('@'):
                        at, line = split(line)
                        ats.append(At(at, line))
                        ats_in_this_comment.add(at)
                    else:
                        current = rfind_by(ats, lambda at: at.name not in ('extends',))
                        if not current:
                            current = At('_')
                        current.append(line)

                if not ats_in_this_comment & set(['cfg', 'class', 'property']):
                    # collect the js identifier following this block of comments
                    end = p[2]

                    name = match(s, end, function_re)
                    if name:
                        ats.insert(start_of_this_comment, At('method', name))
                    else:
                        name = match(s, end, identifier_re)
                        if name:
                            ats.insert(start_of_this_comment, At('_property', name))

        import pprint
        pprint.pprint(ats)

        # build tree starting from flat ats
        self.classes = []
        for at in ats:
            if at.name == 'class':
                self.classes.append(Class(at.lines))
            else:
                try:
                    self.classes[-1].append_child(at)
                except IndexError:
                    pass

    def pod(self, class_):
        s = """\
=pod

=encoding utf8

"""

        for _, attname, section_header in self.Sections:
            if class_.children[attname]:
                s += "\n\n=head2 %s\n\n" % section_header

                for item in sorted(class_.children[attname], key=lambda i: i.name):
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

filename = sys.argv[1]

Document(open(filename).read()).save_pods()
