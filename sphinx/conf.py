# -*- coding: utf-8 -*-
"""A sphinx config file"""

project = 'collective.zamqp'

import pkg_resources
from sys import path
from datetime import datetime
from email import message_from_string

package = pkg_resources.find_on_path(project, path[0]).next()
metadata = message_from_string(package.get_metadata('PKG-INFO'))

copyright = u'%s, %s <%s>' % (datetime.now().year,
                              metadata['author'],
                              metadata['author-email'])

master_doc = 'index'
html_theme = 'default'
source_suffix = '.rst'
pygments_style = 'sphinx'

version = release = package.version

extensions = [
    'collective.sphinx.includedoc',
    'repoze.sphinx.autointerface',
    'sphinxcontrib.plantuml',
    'sphinxtogithub',
]

html_static_path = [
    '_static'
]

html_style = 'custom.css'
