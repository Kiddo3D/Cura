# Copyright (c) 2015 Ultimaker B.V.
# Cura is released under the terms of the AGPLv3 or higher.

from UM.View.View import View
from UM.View.Renderer import Renderer
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Resources import Resources
from UM.Event import Event, KeyEvent
from UM.Signal import Signal
from UM.Scene.Selection import Selection
from UM.Math.Color import Color
from UM.Mesh.MeshData import MeshData

from UM.View.RenderBatch import RenderBatch
from UM.View.GL.OpenGL import OpenGL

from cura.ConvexHullNode import ConvexHullNode

from PyQt5 import QtCore, QtWidgets

from . import LayerViewProxy

## View used to display g-code paths.
class LayerView(View):
    def __init__(self):
        super().__init__()
        self._shader = None
        self._selection_shader = None
        self._num_layers = 0
        self._layer_percentage = 0 # what percentage of layers need to be shown (SLider gives value between 0 - 100)
        self._proxy = LayerViewProxy.LayerViewProxy()
        self._controller.getScene().sceneChanged.connect(self._onSceneChanged)
        self._max_layers = 10
        self._current_layer_num = 10
        self._current_layer_mesh = None
        self._current_layer_jumps = None
        self._activity = False

        self._solid_layers = 5

    def getActivity(self):
        return self._activity

    def getCurrentLayer(self):
        return self._current_layer_num
    
    def _onSceneChanged(self, node):
        self.calculateMaxLayers()
    
    def getMaxLayers(self):
        return self._max_layers

    def resetLayerData(self):
        self._current_layer_mesh = None
        self._current_layer_jumps = None

    def beginRendering(self):
        scene = self.getController().getScene()
        renderer = self.getRenderer()

        if not self._selection_shader:
            self._selection_shader = OpenGL.getInstance().createShaderProgram(Resources.getPath(Resources.Shaders, "color.shader"))
            self._selection_shader.setUniformValue("u_color", Color(32, 32, 32, 128))

        for node in DepthFirstIterator(scene.getRoot()):
            # We do not want to render ConvexHullNode as it conflicts with the bottom layers.
            # However, it is somewhat relevant when the node is selected, so do render it then.
            if type(node) is ConvexHullNode and not Selection.isSelected(node.getWatchedNode()):
                continue

            if not node.render(renderer):
                if node.getMeshData() and node.isVisible():
                    if Selection.isSelected(node):
                        renderer.queueNode(node, transparent = True, shader = self._selection_shader)
                    layer_data = node.callDecoration("getLayerData")
                    if not layer_data:
                        continue

                    # Render all layers below a certain number as line mesh instead of vertices.
                    if self._current_layer_num - self._solid_layers > -1:
                        start = 0
                        end = 0
                        element_counts = layer_data.getElementCounts()
                        for layer, counts in element_counts.items():
                            if layer + self._solid_layers > self._current_layer_num:
                                break
                            end += counts

                        # This uses glDrawRangeElements internally to only draw a certain range of lines.
                        renderer.queueNode(node, mesh = layer_data, mode = RenderBatch.RenderMode.Lines, range = (start, end))

                    # We currently recreate the current "solid" layers every time a
                    if not self._current_layer_mesh:
                        self._current_layer_mesh = MeshData()
                        for i in range(self._solid_layers):
                            layer = self._current_layer_num - i
                            if layer < 0:
                                continue
                            try:
                                layer_mesh = layer_data.getLayer(layer).createMesh()
                                if not layer_mesh or layer_mesh.getVertices() is None:
                                    continue
                            except:
                                continue
                            if self._current_layer_mesh: #Threading thing; Switching between views can cause the current layer mesh to be deleted.
                                self._current_layer_mesh.addVertices(layer_mesh.getVertices())

                            # Scale layer color by a brightness factor based on the current layer number
                            # This will result in a range of 0.5 - 1.0 to multiply colors by.
                            brightness = (2.0 - (i / self._solid_layers)) / 2.0
                            if self._current_layer_mesh:
                                self._current_layer_mesh.addColors(layer_mesh.getColors() * brightness)
                    if self._current_layer_mesh:
                        renderer.queueNode(node, mesh = self._current_layer_mesh)

                    if not self._current_layer_jumps:
                        self._current_layer_jumps = MeshData()
                        for i in range(1):
                            layer = self._current_layer_num - i
                            if layer < 0:
                                continue
                            try:
                                layer_mesh = layer_data.getLayer(layer).createJumps()
                                if not layer_mesh or layer_mesh.getVertices() is None:
                                    continue
                            except:
                                continue

                            self._current_layer_jumps.addVertices(layer_mesh.getVertices())

                            # Scale layer color by a brightness factor based on the current layer number
                            # This will result in a range of 0.5 - 1.0 to multiply colors by.
                            brightness = (2.0 - (i / self._solid_layers)) / 2.0
                            self._current_layer_jumps.addColors(layer_mesh.getColors() * brightness)

                    renderer.queueNode(node, mesh = self._current_layer_jumps)

    def setLayer(self, value):
        if self._current_layer_num != value:
            self._current_layer_num = value
            if self._current_layer_num < 0:
                self._current_layer_num = 0
            if self._current_layer_num > self._max_layers:
                self._current_layer_num = self._max_layers

            self._current_layer_mesh = None
            self._current_layer_jumps = None
            self.currentLayerNumChanged.emit()

    currentLayerNumChanged = Signal()

    def calculateMaxLayers(self):
        scene = self.getController().getScene()
        renderer = self.getRenderer()
        self._activity = True

        self._old_max_layers = self._max_layers
        ## Recalculate num max layers
        new_max_layers = 0
        for node in DepthFirstIterator(scene.getRoot()):
            layer_data = node.callDecoration("getLayerData")
            if not layer_data:
                continue

            if new_max_layers < len(layer_data.getLayers()):
                new_max_layers = len(layer_data.getLayers()) - 1

        if new_max_layers > 0 and new_max_layers != self._old_max_layers:
            self._max_layers = new_max_layers

            # The qt slider has a bit of weird behavior that if the maxvalue needs to be changed first
            # if it's the largest value. If we don't do this, we can have a slider block outside of the
            # slider. 
            if new_max_layers > self._current_layer_num:
                self.maxLayersChanged.emit()
                self.setLayer(int(self._max_layers))
            else:
                self.setLayer(int(self._max_layers))
                self.maxLayersChanged.emit()

    maxLayersChanged = Signal()
    currentLayerNumChanged = Signal()
    
    ##  Hackish way to ensure the proxy is already created, which ensures that the layerview.qml is already created
    #   as this caused some issues. 
    def getProxy(self, engine, script_engine):
        return self._proxy
    
    def endRendering(self):
        pass
    
    def event(self, event):
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        ctrl_is_active = modifiers == QtCore.Qt.ControlModifier
        if event.type == Event.KeyPressEvent and ctrl_is_active:
            if event.key == KeyEvent.UpKey:
                self.setLayer(self._current_layer_num + 1)
                return True
            if event.key == KeyEvent.DownKey:
                self.setLayer(self._current_layer_num - 1)
                return True
