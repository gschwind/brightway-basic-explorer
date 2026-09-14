# coding=utf-8

from IPython.external.qt_for_kernel import QtGui, QtCore
from IPython.lib.guisupport import get_app_qt4, is_event_loop_running_qt4

import os
import sys
import bw2data

def activity_to_json(act):
    a = dict(act)
    exs = list()
    for e in act.exchanges():
        de = dict(bw2data.get_activity(e["input"]))
        de["amount"] = e["amount"]
        de["formula"] = e.get("formula", None)
        exs.append(de)
    a["exchanges"] = exs
    return a

def activity_to_json_with_params(act, params):
    try:
        from lca_algebraic.params import (
            all_params,
            _complete_and_expand_params,
            _getAmountOrFormula,
        )

        from sympy import Basic
    except:
        raise Exception("lca_algebraic not found, please install it before using show_activity_with_params")

    a = dict(act)
    exs = list()
    for e in act.exchanges():
        de = dict(bw2data.get_activity(e["input"]))

        amount = _getAmountOrFormula(e)

        # Params provided ? Evaluate formulas
        if isinstance(amount, Basic):
            new_params = list(_complete_and_expand_params(params, list(all_params().keys())).items())
            amount = amount.subs(new_params)
            if amount.is_number:
                amount = float(amount.evalf())
            de["computed_amount"] = True

        de["amount"] = amount
        de["formula"] = e.get("formula", None)
        exs.append(de)
    a["exchanges"] = exs
    return a

class QStandardItemRO(QtGui.QStandardItem):
    def __init__(self, *args, data=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditable(False)
        self.setSelectable(True)
        self.setData(data)


class TableModel(QtGui.QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(6)
        self.setHeaderData(0, QtCore.Qt.Orientation.Horizontal, "Name")
        self.setHeaderData(1, QtCore.Qt.Orientation.Horizontal, "Unit")
        self.setHeaderData(2, QtCore.Qt.Orientation.Horizontal, "Category")
        self.setHeaderData(3, QtCore.Qt.Orientation.Horizontal, "Location")
        self.setHeaderData(4, QtCore.Qt.Orientation.Horizontal, "Amount")
        self.setHeaderData(5, QtCore.Qt.Orientation.Horizontal, "Formula")

    def load(self, data):
        self.exchanges = [e for e in data]
        self.root = self.invisibleRootItem()
        for e in data:
            row = [
                QStandardItemRO(str(e.get(k, "-")), data=e)
                for k in ["name", "unit", "categories", "location", "amount", "formula"]
            ]

            if "computed_amount" in e:
               row[-2].setForeground(QtGui.QBrush(QtCore.Qt.GlobalColor.red))

            etype = e.get("type", "unknown")
            if etype == "emission":
                path = os.path.join(os.path.dirname(__file__), "icons", "emission.png")
            elif etype in {"process", "processwithreferenceproduct"}:
                path = os.path.join(os.path.dirname(__file__), "icons", "process.png")
            elif etype == "natural resource":
                path = os.path.join(os.path.dirname(__file__), "icons", "natural_resource.png")
            else:
                path = os.path.join(os.path.dirname(__file__), "icons", "unknown.png")

            row[0].setIcon(QtGui.QIcon(path))
            self.root.appendRow(row)

class ActionMenu(QtGui.QMenu):
    def __init__(self, parent, index):
        super().__init__(parent)
        self.index = index

        self.action_copy = self.addAction("Copy")
        self.action_copy.triggered.connect(self.copy_triggered)

        self.action_copy = self.addAction("Copy Full Reference")
        self.action_copy.triggered.connect(self.copy_full_reference_triggered)

        self.action_explore = self.addAction("Explore")
        self.action_explore.triggered.connect(self.explore_triggered)

    def copy_triggered(self):
        QtGui.QGuiApplication.clipboard().setText(self.index.data())

    def copy_full_reference_triggered(self):
        parent = self.parentWidget()
        v = parent.model.root.child(self.index.row(), 0).data()
        text = (v["database"], v["name"], v.get("location", None), v.get("categories", tuple()), v.get("unit", None))
        QtGui.QGuiApplication.clipboard().setText(str(text))

    def explore_triggered(self):
        self.parentWidget().explore(self.index)


class ActivityWindow(QtGui.QMainWindow):
    keep = dict()

    def __init__(self, activity_json):
        super().__init__()
        self.activity_key = (activity_json["database"], activity_json["code"])

        self.setWindowTitle("Activity Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Create central widget and layout
        central_widget = QtGui.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtGui.QVBoxLayout()
        central_widget.setLayout(layout)

        grid = QtGui.QGridLayout()
        layout.addLayout(grid)

        for i, k in enumerate(["database", "name", "location", "unit", "categories", "type"]):
            grid.addWidget(QtGui.QLabel(f"{k}:"), i, 0)
            x = QtGui.QLabel(f"{str(activity_json.get(k, '-'))}")
            x.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(x, i, 1)
        next_row = grid.rowCount()
        grid.addWidget(QtGui.QLabel("filter:"), next_row, 0)
        self.filter_edit = QtGui.QLineEdit("")
        self.filter_edit.textChanged.connect(self.update_filter)
        grid.addWidget(self.filter_edit, next_row, 1)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        self.ignore_case = QtGui.QCheckBox("Ignore Case")
        self.ignore_case.setChecked(True)
        if hasattr(self.ignore_case, "checkStateChanged"):
            self.ignore_case.checkStateChanged.connect(self.update_filter)
        else:
            self.ignore_case.stateChanged.connect(self.update_filter)
        next_row = grid.rowCount()
        grid.addWidget(self.ignore_case, next_row, 1)
        # Create tree view
        self.tree_view = QtGui.QTreeView()
        layout.addWidget(self.tree_view)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.setAlternatingRowColors(True)

        self.model = TableModel()
        self.model.load(activity_json["exchanges"])
        self.tree_view.setModel(self.model)
        self.tree_view.doubleClicked.connect(self.doubleCliked)
        self.tree_view.setExpandsOnDoubleClick(False)
        self.tree_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectionBehavior.SelectItems)
        #self.tree_view.rightClick.connect(self.rightClick)
        self.tree_view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.context_menu)

    def context_menu(self, point):
        index = self.tree_view.indexAt(point)
        self.action_menu = ActionMenu(self, index)
        self.action_menu.exec(self.tree_view.viewport().mapToGlobal(point))

    def closeEvent(self, ev):
        if self.activity_key in ActivityWindow.keep:
            del ActivityWindow.keep[self.activity_key]
        super().closeEvent(ev)

    def update_filter(self, *args):
        text = self.filter_edit.text()
        if self.ignore_case.isChecked():
            text = text.lower()
            index = self.model.root.index()
            for i in range(self.model.rowCount()):
                v = self.model.root.child(i, 0).data()
                self.tree_view.setRowHidden(i, index, text not in v["name"].lower())
        else:
            index = self.model.root.index()
            for i in range(self.model.rowCount()):
                v = self.model.root.child(i, 0).data()
                self.tree_view.setRowHidden(i, index, text not in v["name"])

    def doubleCliked(self, index):
        self.explore(index)

    def explore(self, index):
        r = index.row()
        v = self.model.root.child(r, 0).data()
        show_activity(bw2data.get_activity((v["database"], v["code"])))

    def show(self, *args, **kwargs):
        super().show(*args, **kwargs)
        self.tree_view.setColumnWidth(0, 400)

class ActivityWindowWithParams(ActivityWindow):
    keep = dict()

    def __init__(self, activity_json, params):
        super().__init__(activity_json)
        self.params = params

    def closeEvent(self, ev):
        if self.activity_key in ActivityWindow.keep:
            del ActivityWindowWithParams.keep[self.activity_key]
        super().closeEvent(ev)

    def explore(self, index):
        r = index.row()
        v = self.model.root.child(r, 0).data()
        show_activity_with_params(bw2data.get_activity((v["database"], v["code"])), self.params)

# Replace IPython version to one compatible with Qt6
def start_event_loop_qt4(app=None):
    """Start the qt event loop in a consistent manner."""
    if app is None:
        app = get_app_qt4([""])
    if not is_event_loop_running_qt4(app):
        app._in_event_loop = True
        if hasattr(app, "exec_"):
            app.exec_()
        else:
            app.exec()
        app._in_event_loop = False
    else:
        app._in_event_loop = True

def _show_activity(cls, activity_json, *args):

    if 'matplotlib' in sys.modules:
        import matplotlib
        if hasattr(matplotlib.backends, "backend"):
            if 'qt' not in matplotlib.backends.backend:
                print("WARNING: ActivityGUI will block, use `%matplotlib qt` to avoid blocking")

    app = get_app_qt4()

    if (window := cls.keep.get((activity_json["database"], activity_json["code"]), None)) is None:
        window = cls(activity_json, *args)
        cls.keep[(activity_json["database"], activity_json["code"])] = window
    window.show()

    if not is_event_loop_running_qt4(app):
        start_event_loop_qt4(app)

    window.activateWindow()

def show_activity(act):
    activity_json = activity_to_json(act)
    _show_activity(ActivityWindow, activity_json)

def show_activity_with_params(act, params):
    activity_json = activity_to_json_with_params(act, params)
    _show_activity(ActivityWindowWithParams, activity_json, params)

def close_all():
    for w in list(ActivityWindow.keep.values()):
        w.close()
