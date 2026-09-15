# coding=utf-8

from IPython.external.qt_for_kernel import QtGui, QtCore
from IPython.lib.guisupport import get_app_qt4, is_event_loop_running_qt4

import re
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

def warn_dialog(msg):
    print(f"WARNING: {msg}")
    w = QtGui.QMessageBox(QtGui.QMessageBox.Icon.Warning, "WARNING", msg)
    w.show()
    w.setMaximumSize(800, 600)
    w.exec()

def fatal_dialog(msg):
    print(f"ERROR: {msg}")
    w = QtGui.QMessageBox(QtGui.QMessageBox.Icon.Critical, "ERROR", msg)
    w.show()
    w.setMaximumSize(800, 600)
    w.exec()

class QStandardItemRO(QtGui.QStandardItem):
    def __init__(self, *args, data=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditable(False)
        self.setSelectable(True)
        self.setData(data)

class ExchangeModel(QtGui.QStandardItemModel):
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

        self.action_copy_ref = self.addAction("Copy Full Reference")
        self.action_copy_ref.triggered.connect(self.copy_full_reference_triggered)

        self.action_copy_code = self.addAction("Copy Activity Code")
        self.action_copy_code.triggered.connect(self.copy_code_triggered)

        if hasattr(self.parentWidget(), "explore"):
            self.action_explore = self.addAction("Explore")
            self.action_explore.triggered.connect(self.explore_triggered)

        if hasattr(self.parentWidget(), "explore_in_new_window"):
            self.action_explore = self.addAction("Explore in new window")
            self.action_explore.triggered.connect(self.explore_in_new_window_triggered)

    def copy_triggered(self):
        QtGui.QGuiApplication.clipboard().setText(self.index.data())

    def copy_full_reference_triggered(self):
        parent = self.parentWidget()
        v = parent.model.root.child(self.index.row(), 0).data()
        text = (v["database"], v["name"], v.get("location", None), v.get("categories", tuple()), v.get("unit", None))
        QtGui.QGuiApplication.clipboard().setText(str(text))

    def copy_code_triggered(self):
        parent = self.parentWidget()
        v = parent.model.root.child(self.index.row(), 0).data()
        text = (v["database"], v["code"])
        QtGui.QGuiApplication.clipboard().setText(str(text))

    def explore_triggered(self):
        self.parentWidget().explore(self.index)

    def explore_in_new_window_triggered(self):
        self.parentWidget().explore_in_new_window(self.index)

class TabBar(QtGui.QTabBar):
    def __init__(self):
        super().__init__()

    def tabSizeHint(self, index):
        value = super().tabSizeHint(index)
        return QtCore.QSize(200, value.height())

    def minimumTabSizeHint(self, index):
        value = super().minimumTabSizeHint(index)
        return QtCore.QSize(100, value.height())


class ActivityWindow(QtGui.QMainWindow):
    keep = list()

    def __init__(self, activity_json, params=None):
        super().__init__()
        self.tabs = dict()
        self.xcount = 0
        self.params = params

        self.setWindowTitle("Activity Viewer")
        self.setMinimumSize(QtCore.QSize(800, 600))

        self.tabs_widget = QtGui.QTabWidget()
        self.tabs_widget.setTabBar(TabBar())
        self.tabs_widget.setTabsClosable(True)
        self.tabs_widget.setMovable(True)
        self.tabs_widget.tabCloseRequested.connect(self.close_tab)
        self.tabs_widget.setElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.setCentralWidget(self.tabs_widget)
        self.add_activity(activity_json)

    def add_activity(self, activity_json):
        key = (activity_json["database"], activity_json["code"])
        if key in self.tabs:
            activity_widget = self.tabs[key]
            self.tabs_widget.setCurrentWidget(activity_widget)
            return

        activity_widget = ActivityTab(self, activity_json)
        self.tabs[activity_widget.activity_key] = activity_widget
        self.tabs_widget.addTab(activity_widget, f"#{self.xcount} "+activity_json["name"])
        self.tabs_widget.setCurrentWidget(activity_widget)
        activity_widget.tree_view.setColumnWidth(0, 400)
        self.xcount += 1

    def close_tab(self, index):
        w = self.tabs_widget.widget(index)
        del self.tabs[w.activity_key]
        self.tabs_widget.removeTab(index)

    def closeEvent(self, ev):
        ActivityWindow.keep.remove(self)
        super().closeEvent(ev)

class ActivityTab(QtGui.QWidget):
    def __init__(self, xparent, activity_json):
        super().__init__()

        self.xparent = xparent
        self.activity_key = (activity_json["database"], activity_json["code"])

        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)

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

        self.model = ExchangeModel()
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
        act = bw2data.get_activity((v["database"], v["code"]))
        if self.xparent.params is None:
            activity_json = activity_to_json(act)
        else:
            activity_json = activity_to_json_with_params(act, self.xparent.params)
        self.xparent.add_activity(activity_json)

    def explore_in_new_window(self, index):
        r = index.row()
        v = self.model.root.child(r, 0).data()
        act = bw2data.get_activity((v["database"], v["code"]))
        show_activity(act, self.xparent.params)

class SearchModel(QtGui.QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHeaderData(0, QtCore.Qt.Orientation.Horizontal, "Name")
        self.setHeaderData(1, QtCore.Qt.Orientation.Horizontal, "Unit")
        self.setHeaderData(2, QtCore.Qt.Orientation.Horizontal, "Category")
        self.setHeaderData(3, QtCore.Qt.Orientation.Horizontal, "Location")

    def load(self, data):
        self.exchanges = [e for e in data]
        self.root = self.invisibleRootItem()
        for e in data:
            row = [
                QStandardItemRO(str(e.get(k, "-")), data=e)
                for k in ["name", "unit", "categories", "location"]
            ]

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

class SearchWindow(QtGui.QMainWindow):
    def __init__(self, db, keywords=""):
        super().__init__()

        self.db = db

        self.setWindowTitle("Search Activity")
        self.setMinimumSize(QtCore.QSize(800, 600))

        central_widget = QtGui.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtGui.QVBoxLayout()
        central_widget.setLayout(layout)

        grid = QtGui.QGridLayout()
        layout.addLayout(grid)

        next_row = grid.rowCount()
        grid.addWidget(QtGui.QLabel("database:"), next_row, 0)
        grid.addWidget(QtGui.QLabel(self.db.name), next_row, 1)

        # Keyword query
        next_row = grid.rowCount()
        grid.addWidget(QtGui.QLabel("keywords:"), next_row, 0)
        self.keywords = QtGui.QLineEdit("")
        self.keywords.setText(keywords)
        self.keywords.returnPressed.connect(self.update_search)
        grid.addWidget(self.keywords, next_row, 1)
        self.keywords_button = QtGui.QPushButton("Update")
        self.keywords_button.clicked.connect(self.update_search)

        grid.addWidget(self.keywords_button, next_row, 2)

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
        self.tree_view.doubleClicked.connect(self.doubleCliked)
        self.tree_view.setExpandsOnDoubleClick(False)
        self.tree_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectionBehavior.SelectItems)
        self.tree_view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.context_menu)

        self.model = None

        self.update_search()

    def update_search(self):
        text = self.keywords.text()
        keywords = [re.sub("[^a-zA-Z0-9_-]", "", s) for s in text.split(" ") if len(s) > 0]
        if all(len(x) < 3 for x in keywords):
            warn_dialog("Too smalls keywords")
            return

        acts = self.db.search(" ".join(keywords), proxy=True, limit=200)
        acts = [dict(a) for a in acts]

        old_model = self.model
        self.model = SearchModel()
        self.model.load(acts)
        self.tree_view.setModel(self.model)
        if old_model is not None:
            old_model.deleteLater()
        self.tree_view.setColumnWidth(0, 400)

    def context_menu(self, point):
        index = self.tree_view.indexAt(point)
        self.action_menu = ActionMenu(self, index)
        self.action_menu.exec(self.tree_view.viewport().mapToGlobal(point))

    def update_filter(self, *args):
        if self.model is None:
            return

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
        self.explore_in_new_window(index)

    def explore_in_new_window(self, index):
        r = index.row()
        v = self.model.root.child(r, 0).data()
        act = bw2data.get_activity((v["database"], v["code"]))
        show_activity(act)

    def show(self, *args, **kwargs):
        self.tree_view.setColumnWidth(0, 400)
        super().show(*args, **kwargs)


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

def show_activity(act, params=None):

    if 'matplotlib' in sys.modules:
        import matplotlib
        if hasattr(matplotlib.backends, "backend"):
            if 'qt' not in matplotlib.backends.backend:
                print("WARNING: ActivityGUI will block, use `%matplotlib qt` to avoid blocking")

    app = get_app_qt4()

    if isinstance(act, tuple):
        act = bw2data.get_activity(act)

    if params is None:
        activity_json = activity_to_json(act)
    else:
        activity_json = activity_to_json_with_params(act, params)

    window = ActivityWindow(activity_json, params)
    ActivityWindow.keep.append(window)
    window.show()

    if not is_event_loop_running_qt4(app):
        start_event_loop_qt4(app)

    window.activateWindow()

def search(database, keywords=""):

    if 'matplotlib' in sys.modules:
        import matplotlib
        if hasattr(matplotlib.backends, "backend"):
            if 'qt' not in matplotlib.backends.backend:
                print("WARNING: ActivityGUI will block, use `%matplotlib qt` to avoid blocking")

    app = get_app_qt4()

    if isinstance(database, str):
        if database not in bw2data.databases:
            fatal_dialog(f"Database {database} not found !")
            return
        database = bw2data.Database(database)

    window = SearchWindow(database, keywords)
    window.show()

    if not is_event_loop_running_qt4(app):
        start_event_loop_qt4(app)

    window.activateWindow()
    return window

def close_all():
    for w in list(ActivityWindow.keep):
        w.close()
