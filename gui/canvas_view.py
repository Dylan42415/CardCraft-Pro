from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QWheelEvent, QMouseEvent, QPainter, QPixmap, QColor, QPen, QBrush, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem

class InteractiveCanvasView(QGraphicsView):
    # Signals for slot interactions
    slot_clicked = Signal(int)       # Slot index clicked
    file_dropped_on_slot = Signal(int, str)  # Slot index, Filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Rendering hints for crisp text & images
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Panning state
        self._is_panning = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._zoom_level = 1.0
        
        # Accept drops
        self.setAcceptDrops(True)

    def set_scene_rect(self, w: float, h: float):
        """Sets the size of the canvas scene."""
        self.scene.setSceneRect(0, 0, w, h)

    def wheelEvent(self, event: QWheelEvent):
        """Zooms the canvas on mouse scroll."""
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor
            
        new_zoom = self._zoom_level * zoom_factor
        # Constrain zoom level
        if 0.1 <= new_zoom <= 20.0:
            self._zoom_level = new_zoom
            self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event: QMouseEvent):
        """Handles panning triggers and slot selection clicks."""
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.ShiftModifier):
            self._is_panning = True
            self._pan_start_x = event.position().x()
            self._pan_start_y = event.position().y()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.transform())
            if item:
                val = item.data(0)
                if val is not None:
                    self.slot_clicked.emit(int(val))
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Performs panning translation."""
        if self._is_panning:
            dx = event.position().x() - self._pan_start_x
            dy = event.position().y() - self._pan_start_y
            
            # Scroll scrollbars to pan
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - dx)
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - dy)
            
            self._pan_start_x = event.position().x()
            self._pan_start_y = event.position().y()
            event.accept()
            return
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Ends panning mode."""
        if event.button() == Qt.MouseButton.MiddleButton or (self._is_panning and event.button() == Qt.MouseButton.LeftButton):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
            
        super().mouseReleaseEvent(event)

    def reset_view(self):
        """Fits the sheet scene inside the canvas viewport."""
        self._zoom_level = 1.0
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # Drag and Drop Implementation
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # Check if dropped files contain tiff extensions
            for url in event.mimeData().urls():
                filename = url.toLocalFile()
                if filename.lower().endswith(('.tiff', '.tif')):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            files = [url.toLocalFile() for url in event.mimeData().urls()]
            # Find which graphics item the mouse was dropped onto
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.transform())
            
            # Find if item is a slot or child of a slot
            slot_idx = -1
            if item:
                # If we store slot index in item's data
                val = item.data(0)
                if val is not None:
                    slot_idx = int(val)
            
            if slot_idx != -1 and files:
                # Emit slot dropped file
                self.file_dropped_on_slot.emit(slot_idx, files[0])
                event.acceptProposedAction()
                return
                
        super().dropEvent(event)
