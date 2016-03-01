import os
import subprocess
import sys
import tempfile

from UM.Application import Application
from UM.Logger import Logger
from UM.Mesh.MeshWriter import MeshWriter
from UM.Mesh.WriteMeshJob import WriteMeshJob
from UM.Message import Message
from UM.OutputDevice import OutputDeviceError
from UM.OutputDevice.OutputDevice import OutputDevice
from UM.Preferences import Preferences
from UM.Scene.Iterator.BreadthFirstIterator import BreadthFirstIterator
from UM.i18n import i18nCatalog


catalog = i18nCatalog("cura")

class KiddoPrinter(OutputDevice):
    def __init__(self):
        OutputDevice.__init__(self, "KiddoPrinter")
        self.setName(catalog.i18nc("@item:inmenu", "Print"))
        self.setShortDescription(catalog.i18nc("@action:button", "Print with Kiddo"))
        self.setDescription(catalog.i18nc("@info:tooltip", "Print with Kiddo"))
        self.setIconName("print")
        self.setPriority(1)
        self._writing = False

    def requestWrite(self, node, file_name=None, filter_by_machine=False):
        if self._writing:
            raise OutputDeviceError.DeviceBusyError()

        file_formats = Application.getInstance().getMeshFileHandler().getSupportedFileTypesWrite()
        machine_file_formats = Application.getInstance().getMachineManager().getActiveMachineInstance().getMachineDefinition().getFileFormats()
        file_formats = list(filter(lambda file_format: file_format["mime_type"] in machine_file_formats, file_formats))
        if len(file_formats) == 0:
            Logger.log("e", "There are no file formats available to write with!")
            raise OutputDeviceError.WriteRequestFailedError()
        writer = Application.getInstance().getMeshFileHandler().getWriterByMimeType(file_formats[0]["mime_type"])
        extension = file_formats[0]["extension"]

        if file_name == None:
            for n in BreadthFirstIterator(node):
                if n.getMeshData():
                    file_name = n.getName()
                    if file_name:
                        break

        if not file_name:
            Logger.log("e", "Could not determine a proper file name when trying to print, aborting")
            raise OutputDeviceError.WriteRequestFailedError()

        temp_dir = os.path.join(tempfile.gettempdir(), "Kiddo")
        if not os.path.exists(temp_dir):
            os.mkdir(temp_dir)

        if extension:
            extension = "." + extension
        file_name = os.path.join(temp_dir, os.path.splitext(file_name)[0] + extension)
        
        try:
            Logger.log("d", "Writing to %s", file_name)
            stream = open(file_name, "wt")
            job = WriteMeshJob(writer, stream, node, MeshWriter.OutputMode.TextMode)
            job.setFileName(file_name)
            job.progress.connect(self._onProgress)
            job.finished.connect(self._onFinished)

            message = Message(catalog.i18nc("@info:progress", "Preparing print job"), 0, False, -1)
            message.show()

            self.writeStarted.emit(self)

            job._message = message
            self._writing = True
            job.start()
        except PermissionError as e:
            Logger.log("e", "Permission denied when trying to write to %s: %s", file_name, str(e))
            raise OutputDeviceError.PermissionDeniedError(e)
        except OSError as e:
            Logger.log("e", "Operating system would not let us write to %s: %s", file_name, str(e))
            raise OutputDeviceError.WriteRequestFailedError(e)

    def _onProgress(self, job, progress):
        if hasattr(job, "_message"):
            job._message.setProgress(progress)
        self.writeProgress.emit(self, progress)

    def _onFinished(self, job):
        if hasattr(job, "_message"):
            job._message.hide()
            job._message = None

        job.getStream().close()
        self._writing = False
        self.writeFinished.emit(self)
        try:
            if not job.getResult():
                raise Exception(job.getError())
            self._openSmartControl(job.getFileName())
            self.writeSuccess.emit(self)
        except Exception as e:
            Logger.log("e", str(e))
            message = Message(catalog.i18nc("@info:status", "Error: {0}").format(str(e)))
            message.show()
            self.writeError.emit(self)
            try:
                os.remove(job.getFileName())
            except Exception:
                pass

    def _openSmartControl(self, file_name):
        smart_control_location = Preferences.getInstance().getValue("smart_control/location")
        if not smart_control_location:
            smart_control_location = os.path.join(Application.getInstallPrefix(), "bin", "SmartControl")
            if hasattr(sys, "frozen"):
                smart_control_location = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "..", "SmartControl", "SmartControl")
            if sys.platform == "win32":
                smart_control_location += ".exe"
            smart_control_location = os.path.abspath(smart_control_location)
            Preferences.getInstance().addPreference("smart_control/location", smart_control_location)
        
        Logger.log("d", "Calling SmartControl with file %s", file_name)
        try:
            subprocess.call([smart_control_location, file_name, "--temp-file"])
        except OSError as e:
            raise Exception(catalog.i18nc("@info:status", "Could not open SmartControl at {0}: {1}").format(smart_control_location, str(e)))
