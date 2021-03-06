# Copyright (c) 2015 Ultimaker B.V.
# Uranium is released under the terms of the AGPLv3 or higher.

from UM.Tool import Tool
from UM.Scene.Selection import Selection
from UM.Application import Application
from UM.Qt.ListModel import ListModel

from . import PerObjectSettingsModel

class PerObjectSettingsTool(Tool):
    def __init__(self):
        super().__init__()
        self._model = None

        self.setExposedProperties("Model", "SelectedIndex")

    def event(self, event):
        return False

    def getModel(self):
        if not self._model:
            self._model = PerObjectSettingsModel.PerObjectSettingsModel()

        #For some reason, casting this model to itself causes the model to properly be cast to a QVariant, even though it ultimately inherits from QVariant.
        #Yeah, we have no idea either...
        return PerObjectSettingsModel.PerObjectSettingsModel(self._model)

    def getSelectedIndex(self):
        selected_object_id = id(Selection.getSelectedObject(0))
        index = self.getModel().find("id", selected_object_id)
        return index