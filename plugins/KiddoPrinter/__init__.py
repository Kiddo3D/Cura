from UM.i18n import i18nCatalog

from . import KiddoPrinterPlugin


catalog = i18nCatalog("cura")

def getMetaData():
    return {
        "plugin": {
            "name": catalog.i18nc("@label", "Kiddo printer"),
            "author": "Kiddo",
            "version": "1.0",
            "api": 2,
            "description": catalog.i18nc("@info:whatsthis", "Accepts G-Code and sends it to a Kiddo printer.")
        }
    }

def register(app):
    return { "output_device": KiddoPrinterPlugin.KiddoPrinterPlugin() }
