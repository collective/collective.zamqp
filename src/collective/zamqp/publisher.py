# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###

# BBB for affinitic.zamqp

from zope.deprecation import deprecated, moved

from collective.zamqp.producer import Producer


Publisher = Producer
deprecated('Publisher',
           'Publisher is no more. Please, use Producer instead.')

moved('collective.zamqp.producer', 'version 1.0.0')
