# -*- coding: utf-8 -*-

from Products.CMFCore.utils import getToolByName

from collective.zamqp.interfaces import IConsumingRequest


def setLanguageBindings(site, event):
    # Fixes issue where language bindings are not set, because language tool
    # check explicitly for HTTPRequest, which AMQPRequest only inherits.
    request = getattr(event, 'request', None)
    if not IConsumingRequest.providedBy(request):
        return
    portal_languages = getToolByName(site, 'portal_languages')
    portal_languages.setLanguageBindings()
