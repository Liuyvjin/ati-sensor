from OpenGL.GL import *
import numpy as np
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer
from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem
import pyqtgraph.opengl as gl

from pyati.ati_sensor import ATISensor

class GLAxisItem(GLGraphicsItem):
    """
    可视化一个坐标系
    """
    def __init__(self, size=(10,10,10), width=2, antialias=True, glOptions='opaque'):
        GLGraphicsItem.__init__(self)
        self.setGLOptions(glOptions)
        self.antialias = antialias  # 抗锯齿
        self.size = size  # 三轴长度
        self.width = width  # 线宽
        self.cube_data = np.array([[1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, -1],
                          [1, -1,  1], [1, 1,  1], [-1, 1,  1], [-1, -1,  1]]) * self.size
        self.cube_edges = np.array([0,1,2,3,0,4,5,6,7,4,5,1,2,6,7,3], np.uint32)
        self.update()

    def paint(self):
        self.setupGLState()

        if self.antialias:
            glEnable(GL_LINE_SMOOTH)
            glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        glLineWidth(self.width)  # 设置线宽

        glBegin( GL_LINES )
        x,y,z = self.size
        glColor4f(0, 0.8, 0, .8)  # z is green
        glVertex3f(0, 0, -z)
        glVertex3f(0, 0, z)

        glColor4f(0.7, 0.7, 0, .8)  # y is yellow
        glVertex3f(0, -y, 0)
        glVertex3f(0, y, 0)

        glColor4f(0, 0, 0.8, .8)  # x is blue
        glVertex3f(-x, 0, 0)
        glVertex3f(x, 0, 0)
        glEnd()
        glColor4f(0.7, 0.7, 0.7, .8)  # cube
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointerf(self.cube_data)
        glDrawElements(GL_LINE_LOOP, self.cube_edges.shape[0], GL_UNSIGNED_INT, self.cube_edges)
        glDisableClientState(GL_COLOR_ARRAY)


class GLArrowPlotItem(GLGraphicsItem):
    """可视化箭头"""
    def __init__(self, start_pt=(0,0,0), end_pt=(0,0,0), glOptions='translucent'):
        super().__init__()
        self.setGLOptions(glOptions)
        self.start_pt = np.array(start_pt)
        self.end_pt = np.array(end_pt)
        self.arrow = np.array([[1, 1, -1], [1, -1, -1], [-1, -1, -1], [-1, 1, -1]]) * 0.25
        self.trans = np.eye(3)
        self.update()

    def get_transform(self, e1):
        """将 z 变换到 e1 的变换矩阵"""
        length = np.linalg.norm(e1)
        if length < 1e-4:
            e1 = np.array([0, 0, 1])
        else:
            e1 = e1 / length
        # 构造标准箭头到目标箭头的旋转矩阵
        e = np.zeros_like(e1)  # e 与 e1 不平行
        if e1[0]==0:
            e[0] = 1
        else:
            e[1] = 1

        e2 = np.cross(e1, e)  # 第一个正交向量 (n, 3)
        e2 = e2 / np.linalg.norm(e2)  # 单位化

        e3 = np.cross(e1, e2)
        return np.stack((e2, e3, e1), axis=0)

    def setData(self, start_pt, end_pt):
        self.start_pt = np.array(start_pt)
        self.end_pt = np.array(end_pt)
        self.trans = self.get_transform(self.end_pt - self.start_pt)
        self.update()

    def paint(self):
        arrow = self.arrow @ self.trans + self.end_pt
        self.setupGLState()
        # 抗锯齿
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        # 设置线宽
        glLineWidth(4)

        glBegin( GL_LINES )
        glColor4f(1, 0, 0, .8)  # red
        # force
        glVertex3f(self.start_pt[0], self.start_pt[1], self.start_pt[2])
        glVertex3f(self.end_pt[0], self.end_pt[1], self.end_pt[2])
        # arraw tip
        glVertex3f(self.end_pt[0], self.end_pt[1], self.end_pt[2])
        glVertex3f(arrow[0,0], arrow[0,1], arrow[0,2])
        glVertex3f(self.end_pt[0], self.end_pt[1], self.end_pt[2])
        glVertex3f(arrow[1,0], arrow[1,1], arrow[1,2])
        glVertex3f(self.end_pt[0], self.end_pt[1], self.end_pt[2])
        glVertex3f(arrow[2,0], arrow[2,1], arrow[2,2])
        glVertex3f(self.end_pt[0], self.end_pt[1], self.end_pt[2])
        glVertex3f(arrow[3,0], arrow[3,1], arrow[3,2])
        glEnd()


class QTextShow(QtWidgets.QWidget):
    def __init__(self, parent, name:str, default:str):
        super().__init__(parent)
        self.setMaximumWidth(450)
        hbox = QtWidgets.QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)
        self.name_label = QtWidgets.QLabel(name, self)
        self.text_editor = QtWidgets.QLineEdit(default, self)
        self.text_editor.setReadOnly(True)
        hbox.addWidget(self.name_label, 1)
        hbox.addWidget(self.text_editor, 3)

    @property
    def value(self):
        return self.text_editor.text()

    @value.setter
    def value(self, val):
        self.text_editor.setText(val)


class GLForceWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.ati = ATISensor(ip="192.168.1.1")
        self.setup_ui()

        self.bias_button.clicked.connect(self.onBias)
        # timer
        self.timer = QTimer()
        self.timer.start(50)  # 每隔 50 毫秒更新一次
        self.timer.timeout.connect(self.onTimeout)


    def setup_ui(self):
        self.setWindowTitle("Demo")
        self.resize(1000, 600)
        self.hbox = QtWidgets.QHBoxLayout(self)
        self.hbox.setContentsMargins(20, 0, 0, 0)
        self.hbox.setSpacing(20)

        self.leftFrame = QtWidgets.QFrame(self)
        self.rightFrame = gl.GLViewWidget(self)
        self.hbox.addWidget(self.leftFrame, 1)
        self.hbox.addWidget(self.rightFrame, 5)

        self.vbox = QtWidgets.QVBoxLayout(self.leftFrame)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(15)

        self.fx_view = QTextShow(self.leftFrame, "Fx", "0")
        self.fy_view = QTextShow(self.leftFrame, "Fx", "0")
        self.fz_view = QTextShow(self.leftFrame, "Fx", "0")
        self.tx_view = QTextShow(self.leftFrame, "Tx", "0")
        self.ty_view = QTextShow(self.leftFrame, "Ty", "0")
        self.tz_view = QTextShow(self.leftFrame, "Tz", "0")
        self.vbox.addWidget(self.fx_view)
        self.vbox.addWidget(self.fy_view)
        self.vbox.addWidget(self.fz_view)
        self.vbox.addWidget(self.tx_view)
        self.vbox.addWidget(self.ty_view)
        self.vbox.addWidget(self.tz_view)

        self.bias_button = QtWidgets.QPushButton("bias", self.leftFrame)
        self.vbox.addWidget(self.bias_button)

        spacer = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.vbox.addItem(spacer)
        self.setup_3d()

    def setup_3d(self):
        gl.GLViewWidget
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # 坐标轴
        self.axis = GLAxisItem(size=(10, 10, 10))
        self.rightFrame.addItem(self.axis)

        # 力
        self.force_item = GLArrowPlotItem()
        self.rightFrame.addItem(self.force_item)
        self.rightFrame.setCameraPosition(pos=QtGui.QVector3D(0, 0, -2), distance=50, elevation=22, azimuth=40)


    def onTimeout(self):
        data = self.ati.data
        force = data[:3]
        self.force_item.setData((0,0,0), force)
        self.fx_view.value = "{:>9.3f}".format(data[0])
        self.fy_view.value = "{:>9.3f}".format(data[1])
        self.fz_view.value = "{:>9.3f}".format(data[2])
        self.tx_view.value = "{:>9.3f}".format(data[3])
        self.ty_view.value = "{:>9.3f}".format(data[4])
        self.tz_view.value = "{:>9.3f}".format(data[5])

    def onBias(self):
        self.ati.tare()


import sys
app = QtWidgets.QApplication(sys.argv)
win = GLForceWidget(None)
win.show()
sys.exit(app.exec_())
