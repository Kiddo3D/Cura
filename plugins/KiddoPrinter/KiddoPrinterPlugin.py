from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin

from . import KiddoPrinter


class KiddoPrinterPlugin(OutputDevicePlugin):
    def __init__(self):
        super().__init__()

    def start(self):
        self.getOutputDeviceManager().addOutputDevice(KiddoPrinter.KiddoPrinter())

    def stop(self):
        pass
