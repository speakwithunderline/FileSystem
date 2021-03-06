# -*- coding: utf-8 -*-
__author__ = "gwyang@yahoo.com"

import sys, os
import time
import concurrent.futures as concur

from PyQt5.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget
from PyQt5.QtWidgets import QFileDialog, QInputDialog, QMenu, QAction
from PyQt5.QtWidgets import QTreeWidgetItem, QLineEdit, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal, QThreadPool, QRunnable
from PyQt5.QtGui import QCursor, QColor, QPalette

from frontend.main_ui import *
import backend
import backend.fake_server
from backend import folder
from backend import client
DEBUG = True

######################################
# TODO add icons for methods
# TODO debug
# TODO test download and upload
######################################

class WFMShelf(QMainWindow, Ui_MainWindow):

    fileSig = pyqtSignal(list)
    fileRefreshSig = pyqtSignal()
    serverRefreshSig = pyqtSignal()
    serverSig = pyqtSignal(list)
    currentPathSig = pyqtSignal()
    warnSig = pyqtSignal(str)
    progressSig = pyqtSignal(str, float)
    finishSig = pyqtSignal(str)

    def __init__(self, title="", max_process_num=None, max_thread_num = None, *args, **kwargs):
        super(WFMShelf, self).__init__(*args, **kwargs)

        # The activated item in file tree
        self.selectedFile = None

        # Setup UI
        self.setupUi(self)

        # Title of the main window
        self.setTitle(title)

        # Current path
        self.currentPathList = []
        self.currentPath = ":/"

        # Icon of application
        iconMain = QtGui.QIcon()
        iconMain.addPixmap(QtGui.QPixmap("icons/gnu.jpg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(iconMain)

        # No window frame
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Global StyleSheet
        self.style = """ 
                        QPushButton{ background-color:#E0E0E0; color:#E0E0E0; } 
                        QTabWidget{ background:#E5E5E5; color:#E5E5E5; }
                        QTreeWidget{ background: #F7F7F7;  }
                    """
        self.setStyleSheet(self.style)

        ###########################
        # Start keep_refreshing
        # TODO: make fileTree and serverList refresh each period
        # threadPool.submit(self.keepFileRefreshing)
        # threadPool.submit(self.kee
        ########################

        # Background of window
        totalPlatte = QPalette()
        ## totalPlatte.setColor(self.backgroundRole(), QColor(192, 253, 123))
        totalPlatte.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('icons/afu.jpg')))
        self.setPalette(totalPlatte)

        self.iconTag = "/:ICON_TAG:/ "
        self.folderIcon = "icons/folder.ico"
        self.fileIcon = "icons/file.ico"

        # Current file list
        self.currentFileList = None

        # File to be copy
        self.copiedItem = None

        self.cutFlag = False

        # Rightmenu of file tree
        self.fileTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.createFileTreeRightMenu()

        # Global process pool
        self.processPool = concur.ProcessPoolExecutor(max_workers=max_process_num)
        self.threadPool = concur.ThreadPoolExecutor(max_workers=max_thread_num)

        ##########################################
        # Global rocess locker
        # when serverlist or fileTree is refreshing,
        # changes( upload, download, copy, paste, delete)
        # for file is not allowed
        self.processLockers = []

        # Cuztomized signal for show fileTree and serverTree
        self.fileSig[list].connect(self.showFileTree)
        self.serverSig[list].connect(self.showServerTree)
        self.fileRefreshSig.connect(self.file_refresh_done)
        self.serverRefreshSig.connect(self.server_refresh_done)
        self.currentPathSig.connect(self.change_currentPath)
        self.warnSig[str].connect(self.lock_warning)
        self.progressSig[str, float].connect(self.task_progress)
        self.finishSig[str].connect(self.task_finish)

        # Configure FileTree
        self.currentFileNode = folder.Folder(1, "root")
        self.file_refresh()

        # U/D tack list
        self.taskList = []
        self.nextTID = 0
        self.maxTID = 65536

    ##############################################
    # *   The following three functions are events
    # when dragging the window, the main window is
    # moved to the position of arrow as a result.
    # *   This is used for non-frame window in Qt.
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()
            self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseMoveEvent(self, QMouseEvent):
        if Qt.LeftButton and self.m_drag:
            self.move(QMouseEvent.globalPos() - self.m_DragPosition)
            QMouseEvent.accept()

    def mouseReleaseEvent(self, QMouseEvent):
        self.m_drag = False
        self.setCursor(QCursor(Qt.ArrowCursor))
    ##############################################

    def file_item_change(self, item):
        if DEBUG:
            if item is not None:
                print('activited item change to: ', item.text(0))
            else:
                print('activited item change to: ', 'None')
        self.selectedFile = item

    def setTitle(self, title):
        if title:
            self.setWindowTitle(title)
        return self

    def lock_warning(self, msg, wait_time=0.8):
        self.statusBar().showMessage(msg)
        time.sleep(wait_time)

        if len(self.processLockers) == 1:
            if self.processLockers[0] == "file_locker":
                self.statusBar().showMessage("file refreshing...")
            elif self.processLockers[1] == "server_locker":
                self.statusBar().showMessage("server refreshing...")
        elif len(self.processLockers) == 2:
            self.statusBar().showMessage("file and server refreshing...")

    def change_currentPath(self):
        self.currentPathLine.setText(self.currentPath)

    def file_copy(self):
        if self.selectedFile is not None:
            name = self.selectedFile.text(0)
            for item in self.currentFileList:
                if item['name'] == name:
                    self.curFlag = False
                    self.copiedItem = item
                    self.warnSig[str].emit(self.currentPath + "/" + name + " to be copy.")

            if DEBUG:
                print("COPY, ", )
                if self.copiedItem == None:
                    print("no selected file")
                else:
                    print("selected file: ", self.copiedItem['name'])

    def file_cut(self):
        name = self.selectedFile.text(0)
        for item in self.currentFileList:
            if item['name'] == name:
                self.cutFlag = True
                self.copiedItem = item
                self.warnSig[str].emit(self.currentPath + "/" + name + " to be cut.")

        if DEBUG:
            print("CUT, ", )
            if self.copiedItem == None:
                print("no selected file")
            else:
                print("selected file: ", self.copiedItem['name'])

    def file_paste(self):
        try:
            if DEBUG:
                print("PASTE: from ", self.copiedItem['name'], " to ", self.currentFileNode.folder_name)

            self.threadPool.submit(self.file_paste_method)
        except:
            print("meow")

    def file_paste_method(self):
        self.currentFileNode.paste(self.copiedItem)
        print('file pasted')
        if self.cutFlag:
            self.file_delete_method(self.copiedItem)
            self.curFlag = False

            if DEBUG:
                print("CUTED ", self.copiedItem['name'])

        self.file_refresh_thread()

    def file_delete(self):
        if DEBUG:
            print("DELETE ", self.selectedFile)
        if self.selectedFile != None:
            name = self.selectedFile.text(0)
            msgBox = QMessageBox.information(self,
                                            "Warning",
                                            "确定删除文件 " + name + " ？",
                                            QMessageBox.Yes | QMessageBox.No)
            if msgBox == QMessageBox.Yes:
                if DEBUG:
                    print("DELETE ", name)

                deletedItem = self.query_item(name)
                if deletedItem is not None:
                    self.threadPool.submit(self.file_delete_method, deletedItem)

    def file_delete_method(self, deletedItem):
        folder.Folder.delete(deletedItem)
        self.file_refresh_thread()

    def query_item(self, name):
        ret = None
        for item in self.currentFileList:
            if item['name'] == name:
                ret = item
        return ret

    def deleteTree(self, QTree):
        """
        Make a subtree of QTreeWidget Empty
        :param QTree: QTreeWidget
        :return: None
        """
        num = QTree.topLevelItemCount()
        while num != 0:
            QTree.takeTopLevelItem(0)
            num = QTree.topLevelItemCount()

    def addChildren(self, root, itemList, names):
        """
        add items in list to a node of QTreeWidget as children
        :param root: node to add children
        :param itemList: list of nodes to be added
        :param names: names in the QTreeWidget
        :return: None
        """
        num = len(names)
        print(itemList)
        for item in itemList:
            child = QTreeWidgetItem(root)
            if "is_folder" in item:
                child.setIcon(0, QtGui.QIcon(item["is_folder"][len(self.iconTag):]))
            for i in range(num):
                child.setText(i, str(item[names[i]]))

            if "children" in item:
                self.addChildren(child, item["children"], names)

    def showServerTree(self, serverTree):
        self.deleteTree(self.serverTree)
        self.addChildren(self.serverTree,
                         serverTree,
                         ["id", "ip", "used", "remain"])

    def server_refresh_thread(self):
        self.processLockers.append("server_locker")

        if self.statusBar().currentMessage() == "file refreshing...":
            self.statusBar().showMessage("file and server refreshing...")
        else:
            self.statusBar().showMessage("server refreshing...")

        serverList = backend.fake_server.get_server_list()

        self.serverSig[list].emit(serverList)
        self.serverRefreshSig.emit()

        # delete server_locker
        self.processLockers = list(filter(
            lambda item: item != "server_locker",
            self.processLockers
        ))

    def server_refresh_done(self):
        if self.statusBar().currentMessage() == "server refreshing...":
            self.statusBar().showMessage("server refresh done")
            time.sleep(0.8)
            self.statusBar().showMessage("")
        elif self.statusBar().currentMessage() == "file and server refreshing...":
            self.statusBar().showMessage("file refreshing...")
        else:
            temp = self.statusBar().currentMessage()
            self.statusBar().showMessage("server refresh done")
            time.sleep(0.8)
            self.statusBar().showMessage(temp)

    def server_refresh(self):
        if DEBUG:
            print("server refresh")

        if not ("server_locker" in self.processLockers):
            self.threadPool.submit(self.server_refresh_thread)

    def showFileTree(self, fileTree):
        self.deleteTree(self.fileTree)
        for item in fileTree:
            item["size"] = str(item["size"])
        self.addChildren(self.fileTree,
                          fileTree,
                          ["name", "size", "date"])

    def file_refresh_thread(self):
        if "file_locker" not in self.processLockers:
            self.processLockers.append("file_locker")

        if self.statusBar().currentMessage() == "server refreshing...":
            self.statusBar().showMessage("file and server refreshing...")
        else:
            self.statusBar().showMessage("file refreshing...")


        fileList = self.currentFileNode.get_children()
        if fileList == "error":
            flag = True
            for i in range(10):
                curFileList = self.currentFileNode.get_children()
                if curFileList != "error":
                    self.currentFileList = curFileList
                    flag = False
                    break
                if flag:
                    print("refresh failed...")
        else:
            self.currentFileList = fileList

        if self.currentFileNode.folder_id != 1:
            self.currentFileList.insert(0, {"is_folder": True,
                                "name": "..",
                                "size": "",
                                "date": ""})
        print('get children succeed')
        for item in self.currentFileList:
            if item["is_folder"]:
                item["is_folder"] = self.iconTag + self.folderIcon
            else:
                item["is_folder"] = self.iconTag + self.fileIcon

        self.fileSig[list].emit(self.currentFileList)
        self.fileRefreshSig.emit()

    def file_refresh_done(self):
        if self.statusBar().currentMessage() == "file refreshing...":
            self.statusBar().showMessage("file refresh done")
            time.sleep(0.8)
            self.statusBar().showMessage("")
        elif self.statusBar().currentMessage() == "file and server refreshing...":
            self.statusBar().showMessage("server refreshing...")
        else:
            temp = self.statusBar().currentMessage()
            self.statusBar().showMessage("file refresh done")
            time.sleep(0.8)
            self.statusBar().showMessage(temp)

        # delete file_locker
        self.processLockers = list(filter(
        lambda item: item != "file_locker",
            self.processLockers
            ))
        print('refresh end')

    def file_refresh(self):
        if DEBUG:
            print("file refresh")

        if not ("file_locker" in self.processLockers):
            self.threadPool.submit(self.file_refresh_thread)

    def enter_folder(self):
        if not ("file_locker" in self.processLockers) \
                and self.fileTree.currentItem() is not None:
            subFolderName = self.fileTree.currentItem().text(0)
            if subFolderName == "..":
                self.go_back()
            else:
                subFolder = self.query_item(subFolderName)
                if subFolder is not None and subFolder["is_folder"]:
                    self.processLockers.append("file_locker")
                    self.threadPool.submit(self.enter_folder_method, subFolder)
        elif DEBUG:
            print("File refreshing, so we can't enter folder.")

    def enter_folder_method(self, subFolder):
        self.currentFileNode = self.currentFileNode.go_into_child(
            subFolder["id"], subFolder["name"])
        print('node changed')
        self.currentPathList.append(subFolder['name'])
        self.currentPath = ":/" + "/".join(self.currentPathList)
        self.currentPathSig.emit()
        self.file_refresh_thread()

    def go_back(self):
        if not ("file_locker" in self.processLockers):
            if self.currentFileNode.folder_id != 1:
                self.processLockers.append("file_locker")
                self.threadPool.submit(self.go_back_method)
        elif DEBUG:
            print("File refreshing, so we can't enter folder.")

    def go_back_method(self):
        self.currentFileNode = self.currentFileNode.go_back_father()
        if len(self.currentPathList) > 0:
            self.currentPathList.pop()
            self.currentPath = ":/" + "/".join(self.currentPathList)
            self.currentPathSig.emit()
        self.file_refresh_thread()

    def change_name(self):
        newName, ok = QInputDialog.getText(self, u"改变文件名", u"新文件名: ", QLineEdit.Normal, "")
        newName = self.check_name(newName)
        if ok and newName is not None:
            name = self.selectedFile.text(0)
            changedItem = self.query_item(name)
            if changedItem is not None:
                if changedItem['is_folder']:
                    self.currentFileNode.change_folder_name(changedItem['id'], newName)
                else:
                    self.currentFileNode.change_file_name(changedItem['id'], newName)
                self.file_refresh()

    def new_folder(self):
        name, ok = QInputDialog.getText(self, u"新建文件夹", u"文件夹名: ", QLineEdit.Normal, "")
        if ok:
            name = self.check_name(name)
            if name is not None:
                newItem = QTreeWidgetItem(self.fileTree)
                newItem.setIcon(0, QtGui.QIcon(self.folderIcon))
                newItem.setText(0, name)
                newItem.setText(1, "")
                newItem.setText(2, "")
                self.fileTree.addTopLevelItem(newItem)
                self.threadPool.submit(self.new_folder_method, name)

    def check_name(self, name):
        while self.query_item(name) is not None:
            name, ok = QInputDialog.getText(self, u"文件名重复或非法，请修改", u"更改后的文件名: ", QLineEdit.Normal, "")

            if ok == "":
                return None
        return name



    def new_folder_method(self, name):
            self.currentFileNode.add_folder(name)
            self.file_refresh_thread()

    def file_download(self):
        if self.selectedFile is not None:
            obj_file = self.query_item(self.selectedFile.text(0))
            if obj_file is not None:
                file_path, ok = QFileDialog.getSaveFileName(
                    self,
                    "文件保存",
                    self.selectedFile.text(0),
                    "All Files (*)")
                if ok != "":
                    if len(self.processLockers) == 0:
                        if DEBUG:
                            print('start download: ', obj_file['name'])
                            print('            to: ', file_path)
                            curTID = str(self.nextTID)
                            self.nextTID = (self.nextTID + 1) % self.maxTID
                            newTask = {
                                "TID": curTID,
                                "name": obj_file['id'],
                                "u/d": "download",
                                "progress": "0.0 %",
                                "path": self.currentPath
                            }
                            self.taskList.append(newTask)
                            self.deleteTree(self.taskTree)
                            self.addChildren(self.taskTree, self.taskList, ["TID", "name", "u/d", "progress", "path"])
                            self.processPool.submit(folder.Folder.download_file,
                                                    curTID,
                                                    obj_file['id'],
                                                    file_path,
                                                    self.progressSig,
                                                    self.finishSig )
                    elif DEBUG:
                        print("information refreshing, cannot download")
                        self.warnSig[str].emit("Infomation refreshing, cannot download now")
                        # self.threadPool.submit(self.lock_warning, "Infomation refreshing, cannot download now")
                elif DEBUG:
                    print("Error: invalid save path")

    def file_upload(self):
        file_path, ok = QFileDialog.getOpenFileName(
            self,
            "~/",
            "All files (*)")
        if ok != "":
            if len(self.processLockers) == 0:
                if DEBUG:
                    print('start upload: ', file_path)
                    print('          to: ', self.currentPath)
                    curTID = str(self.nextTID)
                    self.nextTID = (self.nextTID + 1) % self.maxTID
                    newTask = {
                        "TID": curTID,
                        "name": os.path.basename(file_path),
                        "u/d": "upload",
                        "progress": "0.0 %",
                        "path": self.currentPath
                    }
                    self.taskList.append(newTask)
                    self.deleteTree(self.taskTree)
                    self.addChildren(self.taskTree, self.taskList, ["TID", "name", "u/d", "progress", "path"])
                    self.processPool.submit(self.currentFileNode.upload_file,
                                            file_path,
                                            curTID,
                                            self.progressSig,
                                            self.finishSig)
            elif DEBUG:
                print("information refreshing, cannot upload")
                self.warnSig[str].emit("information refreshing, cannot upload")
                # self.threadPool.submit(self.lock_warning, "Infomation refreshing, cannot upload now")
        elif DEBUG:
            print("Error: invalid upload file path")

    def task_progress(self, TID, progress):
        print("Begin task_progress TID:", TID, " Progress", progress)
        count = self.fileTree.topLevelItemCount()
        for i in range(count):
            item = self.fileTree.topLevelItem(i)
            if item.text(0) == TID:
                item.setText(3, str(progress * 100) + '%')
        print("Finish task_progress TID:", TID)

    def task_finish(self, TID):
        count = self.fileTree.topLevelItemCount()
        for i in range(count):
            item = self.fileTree.topLevelItem(i)
            if item.text(0) == TID:
                self.fileTree.takeTopLevelItem(i)
                self.warnSig[str].emit(TID + " finished")
        self.file_refresh()

    ##############################################
    # *   Creat right menu for fileTree
    def file_context(self, point):
        if self.selectedFile is not None:
            self.fileTreeRightMenu.exec_(QCursor.pos())
            self.fileTreeRightMenu.show()

    def createFileTreeRightMenu(self):
        self.fileTreeRightMenu = QMenu(self.fileTree)

        downAction = QAction(QtGui.QIcon("icons/download.ico"), u"&下载", self)
        downAction.triggered.connect(self.file_download)
        self.fileTreeRightMenu.addAction(downAction)

        backAction = QAction(QtGui.QIcon("icons/back.ico"), u"&后退", self)
        backAction.setShortcut("Ctrl+B")
        backAction.triggered.connect(self.go_back)
        self.fileTreeRightMenu.addAction(backAction)

        changeAction = QAction(QtGui.QIcon("icons/rename.ico"), u"&更改文件名", self)
        changeAction.triggered.connect(self.change_name)
        self.fileTreeRightMenu.addAction(changeAction)

        newAction = QAction(QtGui.QIcon("icons/newFolder.ico"), u"&新建文件夹", self)
        newAction.setShortcut("Ctrl+N")
        newAction.triggered.connect(self.new_folder)
        self.fileTreeRightMenu.addAction(newAction)

        refreshAction = QAction(QtGui.QIcon("icons/refresh.ico"), u"&刷新", self)
        refreshAction.setShortcut("F5")
        refreshAction.triggered.connect(self.file_refresh)
        self.fileTreeRightMenu.addAction(refreshAction)

        self.fileTreeRightMenu.addSeparator()

        copyAction = QAction(QtGui.QIcon("icons/copy.ico"), u"&复制", self)
        copyAction.setShortcut("Ctrl+C")
        copyAction.triggered.connect(self.file_copy)
        self.fileTreeRightMenu.addAction(copyAction)

        pasteAction = QAction(QtGui.QIcon("icons/paste.ico"), u"&粘贴", self)
        pasteAction.setShortcut("Ctrl+V")
        pasteAction.triggered.connect(self.file_paste)
        self.fileTreeRightMenu.addAction(pasteAction)

        cutAction = QAction(QtGui.QIcon("icons/cut.ico"), u"&剪切", self)
        cutAction.setShortcut("Ctrl+X")
        cutAction.triggered.connect(self.file_cut)
        self.fileTreeRightMenu.addAction(cutAction)

        deleteAction = QAction(QtGui.QIcon("icons/close.ico"), u"&删除", self)
        deleteAction.setShortcut("Ctrl+D")
        deleteAction.triggered.connect(self.file_delete)
        self.fileTreeRightMenu.addAction(deleteAction)
    ##########################################

if __name__ == "__main__":
    client.init("192.168.1.138", 8080)
    app = QApplication(sys.argv)
    wfm_shelf = WFMShelf(title="Futanari Distributed File Syetem")
    wfm_shelf.show()
    sys.exit(app.exec_())
