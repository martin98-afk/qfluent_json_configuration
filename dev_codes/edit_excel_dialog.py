import os
import sys
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from PyQt5.QtCore import Qt, QFileInfo, QSize
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QHeaderView
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, TabBar, TableWidget, PushButton,
    FluentIcon as FIF, InfoBar, InfoBarPosition, MessageBox, Dialog,
    ComboBox, LineEdit, SearchLineEdit, PrimaryPushButton, SwitchButton,
    CaptionLabel, BodyLabel, TitleLabel, StrongBodyLabel, DropDownPushButton,
    Action, RoundMenu, CommandBar, isDarkTheme, FlyoutView, Flyout, FlyoutAnimationType
)
from loguru import logger
from PyQt5.QtGui import QIcon, QFontMetrics, QTextOption
from PyQt5.QtWidgets import QApplication


class ExcelEditor(FluentWindow):
    """Excel文件编辑器主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Excel 编辑器")
        self.setWindowIcon(QIcon(":/icons/excel.png"))
        self.resize(1200, 800)

        # 当前打开的文件路径
        self.current_file = None
        # 存储所有工作表的数据
        self.sheets_data = {}
        # 当前显示的工作表名称
        self.current_sheet = None
        # 列名计数器
        self.column_counter = 1

        # 创建UI
        self.init_ui()
        # 创建导航
        self.init_navigation()
        # 创建菜单
        self.init_menu()

    def init_ui(self):
        """初始化UI界面"""
        # 创建主内容区域
        self.main_widget = QWidget()
        self.main_widget.setObjectName("mainWidget")
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(20, 10, 20, 20)  # 减少顶部边距，因为CommandBar会占用空间
        self.main_layout.setSpacing(15)

        # 标题区域
        title_layout = QHBoxLayout()
        self.file_path_label = CaptionLabel("未打开文件")
        self.file_path_label.setStyleSheet("font-size: 12px; color: #606060;")
        title_layout.addWidget(self.file_path_label)
        title_layout.addStretch()

        # 创建CommandBar（替换原来的工具栏）
        self.command_bar = CommandBar(self)
        self.command_bar.setFixedHeight(40)
        self.command_bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # 创建操作按钮
        self.open_action = Action(FIF.FOLDER, '打开', self)
        self.save_action = Action(FIF.SAVE, '保存', self)
        self.save_as_action = Action(FIF.SAVE_AS, '另存为', self)
        self.add_row_action = Action(FIF.ADD, '添加行', self)
        self.add_col_action = Action(FIF.ADD, '添加列', self)
        self.delete_row_action = Action(FIF.REMOVE, '删除行', self)
        self.delete_col_action = Action(FIF.REMOVE, '删除列', self)
        self.search_action = Action(FIF.SEARCH, '搜索', self)

        # 添加到CommandBar
        self.command_bar.addAction(self.open_action)
        self.command_bar.addAction(self.save_action)
        self.command_bar.addAction(self.save_as_action)
        self.command_bar.addSeparator()
        self.command_bar.addAction(self.add_row_action)
        self.command_bar.addAction(self.add_col_action)
        self.command_bar.addAction(self.delete_row_action)
        self.command_bar.addAction(self.delete_col_action)
        self.command_bar.addAction(self.search_action)

        # 连接信号
        self.open_action.triggered.connect(self.open_file)
        self.save_action.triggered.connect(self.save_file)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.add_row_action.triggered.connect(self.add_row)
        self.add_col_action.triggered.connect(self.add_column)
        self.delete_row_action.triggered.connect(self.delete_row)
        self.delete_col_action.triggered.connect(self.delete_column)
        self.search_action.triggered.connect(self.show_search_flyout)

        # 禁用所有操作按钮（初始状态）
        self.set_command_bar_enabled(False)

        # 工作表标签栏
        self.tab_bar = TabBar()
        self.tab_bar.tabAddRequested.connect(self.add_new_sheet)
        self.tab_bar.tabCloseRequested.connect(self.close_sheet)
        self.tab_bar.currentChanged.connect(self.switch_sheet)

        # 表格区域
        self.table = TableWidget()
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(True)
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        # 设置表格列名自动换行
        self.setup_table_header_wrapping()

        # 状态栏
        self.status_bar = CaptionLabel("就绪")
        self.status_bar.setStyleSheet("font-size: 12px; color: #606060;")

        # 添加到主布局
        self.main_layout.addLayout(title_layout)
        self.main_layout.addWidget(self.command_bar)
        self.main_layout.addWidget(self.tab_bar)
        self.main_layout.addWidget(self.table)
        self.main_layout.addWidget(self.status_bar)

        # 添加到窗口
        self.addSubInterface(self.main_widget, FIF.DOCUMENT, "工作区")

    def setup_table_header_wrapping(self):
        """设置表格列名自动换行"""
        # 设置表头自动换行
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setCascadingSectionResizes(False)

        # 增加表头高度以适应换行
        self.table.horizontalHeader().setMinimumHeight(60)
        self.table.horizontalHeader().setDefaultSectionSize(120)  # 默认列宽

    def update_table_header_wrapping(self):
        """更新表格列名换行（在列数变化后调用）"""
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item:
                # 设置文本换行
                item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                item.setToolTip(item.text())  # 显示完整列名作为工具提示

    def init_navigation(self):
        """初始化导航栏"""
        # 添加帮助页面
        self.help_widget = QWidget()
        self.help_widget.setObjectName("helpWidget")
        help_layout = QVBoxLayout(self.help_widget)
        help_layout.setContentsMargins(40, 40, 40, 40)
        help_layout.setSpacing(20)

        title = TitleLabel("Excel 编辑器帮助")
        title.setStyleSheet("font-size: 24px;")
        help_layout.addWidget(title)

        desc = BodyLabel("这是一个基于QFluentWidgets的Excel文件编辑器，支持打开、编辑和保存Excel文件。")
        desc.setWordWrap(True)
        help_layout.addWidget(desc)

        features = [
            ("📁", "打开Excel文件 (.xlsx, .xls)"),
            ("💾", "保存修改到原文件"),
            ("🖨", "另存为新文件"),
            ("➕", "添加行/列"),
            ("➖", "删除行/列"),
            ("🔍", "搜索内容"),
            ("📊", "多工作表支持")
        ]

        features_layout = QVBoxLayout()
        for icon, feature in features:
            item = QHBoxLayout()
            icon_label = StrongBodyLabel(icon)
            icon_label.setStyleSheet("font-size: 18px;")
            item.addWidget(icon_label)
            item.addWidget(BodyLabel(feature))
            item.addStretch()
            features_layout.addLayout(item)

        help_layout.addLayout(features_layout)
        help_layout.addStretch()

        self.addSubInterface(self.help_widget, FIF.HELP, "帮助", NavigationItemPosition.BOTTOM)

    def init_menu(self):
        """初始化右键菜单"""
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        """显示右键菜单"""
        menu = RoundMenu(parent=self.table)

        # 单元格操作
        menu.addAction(Action(FIF.EDIT, "编辑单元格", triggered=self.edit_current_cell))
        menu.addSeparator()

        # 行操作
        row_menu = RoundMenu("行操作", self)
        row_menu.addAction(Action(FIF.ADD, "在上方插入行", triggered=lambda: self.insert_row("above")))
        row_menu.addAction(Action(FIF.ADD, "在下方插入行", triggered=lambda: self.insert_row("below")))
        row_menu.addAction(Action(FIF.REMOVE, "删除行", triggered=self.delete_row))
        menu.addMenu(row_menu)

        # 列操作
        col_menu = RoundMenu("列操作", self)
        col_menu.addAction(Action(FIF.ADD, "在左侧插入列", triggered=lambda: self.insert_column("left")))
        col_menu.addAction(Action(FIF.ADD, "在右侧插入列", triggered=lambda: self.insert_column("right")))
        col_menu.addAction(Action(FIF.REMOVE, "删除列", triggered=self.delete_column))
        menu.addMenu(col_menu)

        menu.addSeparator()
        menu.addAction(Action(FIF.COPY, "复制", triggered=self.copy_selection))
        menu.addAction(Action(FIF.PASTE, "粘贴", triggered=self.paste_clipboard))

        menu.exec(self.table.mapToGlobal(pos))

    def show_search_flyout(self):
        """显示搜索浮出控件"""
        view = FlyoutView(
            title="搜索内容",
            content="请输入要搜索的内容：",
            isClosable=True
        )

        # 创建搜索框
        self.search_box = LineEdit()
        self.search_box.setPlaceholderText("搜索内容...")
        self.search_box.setFixedWidth(200)
        self.search_box.returnPressed.connect(lambda: self.search_content(self.search_box.text()))

        view.widgetLayout.addWidget(self.search_box)

        # 创建按钮
        w = PrimaryPushButton("搜索")
        w.setFixedWidth(120)
        w.clicked.connect(lambda: self.search_content(self.search_box.text()))
        view.widgetLayout.addWidget(w, 0, Qt.AlignRight)

        # 显示浮出控件
        Flyout.make(view, self.command_bar.actionButton("search"), self, aniType=FlyoutAnimationType.SLIDE_RIGHT)

    def set_command_bar_enabled(self, enabled):
        """设置CommandBar按钮状态"""
        self.save_action.setEnabled(enabled)
        self.save_as_action.setEnabled(enabled)
        self.add_row_action.setEnabled(enabled)
        self.add_col_action.setEnabled(enabled)
        self.delete_row_action.setEnabled(enabled)
        self.delete_col_action.setEnabled(enabled)

    def open_file(self):
        """打开Excel文件（健壮的引擎选择）"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开Excel文件", "", "Excel Files (*.xlsx *.xls)"
        )

        if not file_path:
            return

        # 尝试的引擎列表（根据文件类型排序）
        engines_to_try = []
        if file_path.lower().endswith('.xlsx'):
            engines_to_try = ['openpyxl', 'xlrd']
        elif file_path.lower().endswith('.xls'):
            engines_to_try = ['xlrd', 'openpyxl']
        else:
            self.create_warningbar("文件格式错误", "不支持的文件扩展名。请使用 .xlsx 或 .xls 文件。")
            return

        excel_file = None
        engine_used = None
        error_messages = []

        # 尝试所有可能的引擎
        for engine in engines_to_try:
            try:
                excel_file = pd.ExcelFile(file_path, engine=engine)
                engine_used = engine
                break
            except Exception as e:
                error_messages.append(f"{engine}: {str(e)}")

        # 如果所有引擎都失败
        if excel_file is None:
            # 检查是否缺少必要的包
            missing_packages = []
            if 'openpyxl' in [e.split(':')[0] for e in error_messages]:
                try:
                    import openpyxl
                except ImportError:
                    missing_packages.append("openpyxl")

            if 'xlrd' in [e.split(':')[0] for e in error_messages]:
                try:
                    import xlrd
                    # 检查 xlrd 版本是否支持 .xls
                    if file_path.lower().endswith('.xls') and xlrd.__version__ >= '2.0':
                        error_msg = "xlrd 2.0+ 版本不再支持 .xls 文件，请安装 xlrd<2.0"
                        self.create_errorbar("依赖问题", error_msg)
                        return
                except ImportError:
                    missing_packages.append("xlrd<2.0" if file_path.lower().endswith('.xls') else "xlrd")

            # 构建详细的错误消息
            error_msg = "无法打开文件，尝试了以下引擎:\n" + "\n".join(error_messages)
            if missing_packages:
                error_msg += f"\n\n建议安装缺失的包: pip install {' '.join(missing_packages)}"

            self.create_errorbar("文件打开失败", error_msg)
            return

        try:
            # 读取所有工作表
            self.sheets_data = {}
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, engine=engine_used)
                # 确保所有列名都是字符串
                df.columns = [str(col) for col in df.columns]
                self.sheets_data[sheet_name] = df

            # 清空工作表标签
            while self.tab_bar.count() > 0:
                self.tab_bar.removeTab(0)

            # 添加工作表标签
            for sheet_name in self.sheets_data.keys():
                self.tab_bar.addTab(
                    routeKey=sheet_name,
                    text=sheet_name,
                    icon=None
                )

            # 设置当前文件路径
            self.current_file = file_path
            self.file_path_label.setText(f"当前文件: {file_path}")

            # 启用相关按钮
            self.set_command_bar_enabled(True)

            # 显示第一个工作表
            if self.sheets_data:
                self.current_sheet = list(self.sheets_data.keys())[0]
                self.tab_bar.setCurrentTab(self.current_sheet)
                self.display_sheet(self.current_sheet)

            self.status_bar.setText(f"已打开文件: {os.path.basename(file_path)}")
            self.create_successbar("文件打开成功", f"成功打开文件: {os.path.basename(file_path)}")

        except Exception as e:
            self.create_errorbar("文件处理失败", f"无法处理文件内容: {str(e)}")

    def display_sheet(self, sheet_name):
        """显示指定工作表的数据"""
        if sheet_name not in self.sheets_data:
            return

        df = self.sheets_data[sheet_name]

        # 设置表格行列数
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))

        # 设置表头并启用自动换行
        for col, col_name in enumerate(df.columns):
            item = QTableWidgetItem(str(col_name))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            item.setToolTip(str(col_name))  # 显示完整列名作为工具提示
            self.table.setHorizontalHeaderItem(col, item)

        # 更新列名换行
        self.update_table_header_wrapping()

        # 填充数据
        for row in range(len(df)):
            for col in range(len(df.columns)):
                value = df.iat[row, col]
                # 处理NaN值
                if pd.isna(value):
                    value = ""
                else:
                    value = str(value)
                item = QTableWidgetItem(value)
                self.table.setItem(row, col, item)

        self.status_bar.setText(f"显示工作表: {sheet_name} ({len(df)}行, {len(df.columns)}列)")

    def switch_sheet(self, index):
        """切换工作表"""
        if index < 0:
            return

        sheet_name = self.tab_bar.tabText(index)
        self.current_sheet = sheet_name
        self.display_sheet(sheet_name)

    def add_new_sheet(self):
        """添加新工作表"""
        if not self.current_file:
            self.create_warningbar("操作失败", "请先打开一个Excel文件")
            return

        # 创建默认名称的工作表
        base_name = "Sheet"
        i = 1
        while f"{base_name}{i}" in self.sheets_data:
            i += 1
        new_sheet_name = f"{base_name}{i}"

        # 创建空DataFrame
        df = pd.DataFrame(columns=["A", "B", "C"])
        self.sheets_data[new_sheet_name] = df

        # 添加标签
        self.tab_bar.addTab(
            routeKey=new_sheet_name,
            text=new_sheet_name,
            icon=None
        )

        # 切换到新工作表
        self.tab_bar.setCurrentTab(new_sheet_name)
        self.current_sheet = new_sheet_name
        self.display_sheet(new_sheet_name)

        self.status_bar.setText(f"已添加新工作表: {new_sheet_name}")
        self.create_infobar("工作表添加", f"已添加新工作表: {new_sheet_name}")

    def close_sheet(self, index):
        """关闭工作表"""
        if len(self.sheets_data) <= 1:
            self.create_warningbar("操作失败", "至少需要保留一个工作表")
            return

        sheet_name = self.tab_bar.tabText(index)

        # 确认对话框
        title = "确认关闭工作表"
        content = f"确定要关闭工作表 '{sheet_name}' 吗？此操作无法撤销。"
        w = MessageBox(title, content, self)
        if w.exec():
            # 移除工作表
            del self.sheets_data[sheet_name]
            self.tab_bar.removeTab(index)

            # 切换到第一个工作表
            if self.sheets_data:
                first_sheet = list(self.sheets_data.keys())[0]
                self.tab_bar.setCurrentTab(first_sheet)
                self.current_sheet = first_sheet
                self.display_sheet(first_sheet)

            self.status_bar.setText(f"已关闭工作表: {sheet_name}")

    def on_cell_changed(self, row, col):
        """单元格内容变化处理"""
        if not self.current_sheet:
            return

        item = self.table.item(row, col)
        if item is None:
            return

        # 获取当前DataFrame
        df = self.sheets_data[self.current_sheet]

        # 检查索引是否在范围内
        if row >= len(df) or col >= len(df.columns):
            self.create_warningbar("数据不一致", "表格与数据源不同同步，请重新加载文件")
            return

        # 更新DataFrame
        new_value = item.text()
        # 尝试转换为数字
        try:
            if '.' in new_value:
                new_value = float(new_value)
            else:
                new_value = int(new_value)
        except (ValueError, TypeError):
            pass

        # 更新数据
        self.sheets_data[self.current_sheet].iat[row, col] = new_value

    def on_cell_double_clicked(self, row, col):
        """双击单元格编辑"""
        self.table.editItem(self.table.item(row, col))

    def edit_current_cell(self):
        """编辑当前单元格"""
        if self.table.currentRow() >= 0 and self.table.currentColumn() >= 0:
            self.table.editItem(self.table.currentItem())

    def add_row(self):
        """添加行"""
        if not self.current_sheet:
            return

        current_row = self.table.currentRow()
        if current_row < 0:
            current_row = 0

        # 在当前行下方添加新行
        self.table.insertRow(current_row + 1)

        # 更新DataFrame
        df = self.sheets_data[self.current_sheet]
        # 创建与当前DataFrame列数相同的新行
        new_row = pd.DataFrame([[""] * len(df.columns)], columns=df.columns)
        # 插入新行
        self.sheets_data[self.current_sheet] = pd.concat(
            [df.iloc[:current_row + 1], new_row, df.iloc[current_row + 1:]]
        ).reset_index(drop=True)

        # 重新显示表格以确保同步
        self.display_sheet(self.current_sheet)

        self.status_bar.setText(f"已添加行到工作表: {self.current_sheet}")

    def generate_unique_column_name(self, df):
        """生成唯一的列名"""
        base_name = "新列"
        i = self.column_counter
        new_col_name = f"{base_name}{i}"
        while new_col_name in df.columns:
            i += 1
            new_col_name = f"{base_name}{i}"
        self.column_counter = i + 1  # 更新计数器
        return new_col_name

    def add_column(self):
        """添加列"""
        if not self.current_sheet:
            return

        current_col = self.table.currentColumn()
        if current_col < 0:
            current_col = 0

        # 在当前列右侧添加新列
        self.table.insertColumn(current_col + 1)

        # 获取当前DataFrame
        df = self.sheets_data[self.current_sheet]

        # 生成唯一列名
        new_col_name = self.generate_unique_column_name(df)

        # 更新表头
        item = QTableWidgetItem(new_col_name)
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        item.setToolTip(new_col_name)
        self.table.setHorizontalHeaderItem(current_col + 1, item)

        # 更新DataFrame
        try:
            # 在指定位置插入新列
            df.insert(current_col + 1, new_col_name, [""] * len(df))
            self.sheets_data[self.current_sheet] = df

            # 更新列名换行
            self.update_table_header_wrapping()

            self.status_bar.setText(f"已添加列到工作表: {self.current_sheet}")
        except Exception as e:
            self.create_errorbar("添加列失败", f"无法添加列: {str(e)}")
            # 回滚表格操作
            self.table.removeColumn(current_col + 1)

    def delete_row(self):
        """删除行"""
        if not self.current_sheet:
            return

        current_row = self.table.currentRow()
        if current_row < 0:
            self.create_warningbar("操作失败", "请选择要删除的行")
            return

        # 确认对话框
        title = "确认删除行"
        content = f"确定要删除第 {current_row + 1} 行吗？此操作无法撤销。"
        w = MessageBox(title, content, self)
        if w.exec():
            # 删除表格行
            self.table.removeRow(current_row)

            # 更新DataFrame
            df = self.sheets_data[self.current_sheet]
            self.sheets_data[self.current_sheet] = df.drop(index=current_row).reset_index(drop=True)

            # 重新显示表格以确保同步
            self.display_sheet(self.current_sheet)

            self.status_bar.setText(f"已删除行: {current_row + 1}")

    def delete_column(self):
        """删除列"""
        if not self.current_sheet:
            return

        current_col = self.table.currentColumn()
        if current_col < 0:
            self.create_warningbar("操作失败", "请选择要删除的列")
            return

        # 获取列名
        col_item = self.table.horizontalHeaderItem(current_col)
        col_name = col_item.text() if col_item else f"列 {current_col + 1}"

        # 确认对话框
        title = "确认删除列"
        content = f"确定要删除列 '{col_name}' 吗？此操作无法撤销。"
        w = MessageBox(title, content, self)
        if w.exec():
            # 删除表格列
            self.table.removeColumn(current_col)

            # 更新DataFrame
            df = self.sheets_data[self.current_sheet]
            # 检查列是否存在
            if current_col < len(df.columns):
                col_to_drop = df.columns[current_col]
                self.sheets_data[self.current_sheet] = df.drop(columns=[col_to_drop])

                # 重新显示表格以确保同步
                self.display_sheet(self.current_sheet)

                self.status_bar.setText(f"已删除列: {col_name}")
            else:
                self.create_warningbar("删除列失败", "列索引超出范围")

    def insert_row(self, position):
        """插入行（上方或下方）"""
        if not self.current_sheet:
            return

        current_row = self.table.currentRow()
        if current_row < 0:
            current_row = 0

        insert_pos = current_row if position == "above" else current_row + 1

        # 插入表格行
        self.table.insertRow(insert_pos)

        # 更新DataFrame
        df = self.sheets_data[self.current_sheet]
        new_row = pd.DataFrame([[""] * len(df.columns)], columns=df.columns)
        self.sheets_data[self.current_sheet] = pd.concat(
            [df.iloc[:insert_pos], new_row, df.iloc[insert_pos:]]
        ).reset_index(drop=True)

        # 重新显示表格以确保同步
        self.display_sheet(self.current_sheet)

        self.status_bar.setText(f"已{'在上方' if position == 'above' else '在下方'}插入行")

    def insert_column(self, position):
        """插入列（左侧或右侧）"""
        if not self.current_sheet:
            return

        current_col = self.table.currentColumn()
        if current_col < 0:
            current_col = 0

        insert_pos = current_col if position == "left" else current_col + 1

        # 插入表格列
        self.table.insertColumn(insert_pos)

        # 获取当前DataFrame
        df = self.sheets_data[self.current_sheet]

        # 生成唯一列名
        new_col_name = self.generate_unique_column_name(df)

        # 更新表头
        item = QTableWidgetItem(new_col_name)
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        item.setToolTip(new_col_name)
        self.table.setHorizontalHeaderItem(insert_pos, item)

        # 更新DataFrame
        try:
            df.insert(insert_pos, new_col_name, [""] * len(df))
            self.sheets_data[self.current_sheet] = df

            # 更新列名换行
            self.update_table_header_wrapping()

            self.status_bar.setText(f"已{'在左侧' if position == 'left' else '在右侧'}插入列")
        except Exception as e:
            self.create_errorbar("插入列失败", f"无法插入列: {str(e)}")
            # 回滚表格操作
            self.table.removeColumn(insert_pos)

    def copy_selection(self):
        """复制选中的单元格"""
        if not self.table.selectedItems():
            return

        rows = sorted(index.row() for index in self.table.selectedIndexes())
        cols = sorted(index.column() for index in self.table.selectedIndexes())

        row_count = rows[-1] - rows[0] + 1
        col_count = cols[-1] - cols[0] + 1

        clipboard = ""
        for i in range(row_count):
            if i > 0:
                clipboard += "\n"
            for j in range(col_count):
                item = self.table.item(rows[0] + i, cols[0] + j)
                clipboard += item.text() if item else ""
                if j < col_count - 1:
                    clipboard += "\t"

        # 复制到剪贴板
        clipboard_obj = QApplication.clipboard()
        clipboard_obj.setText(clipboard)

        self.status_bar.setText("已复制选中的单元格")

    def paste_clipboard(self):
        """粘贴剪贴板内容"""
        if not self.current_sheet or self.table.currentRow() < 0 or self.table.currentColumn() < 0:
            return

        clipboard = QApplication.clipboard().text()
        if not clipboard:
            return

        # 解析剪贴板内容
        rows = clipboard.split("\n")
        data = [row.split("\t") for row in rows]

        start_row = self.table.currentRow()
        start_col = self.table.currentColumn()

        # 确保表格有足够的行列
        max_row = start_row + len(data) - 1
        max_col = start_col + len(data[0]) - 1

        while self.table.rowCount() <= max_row:
            self.table.insertRow(self.table.rowCount())
        while self.table.columnCount() <= max_col:
            self.table.insertColumn(self.table.columnCount())

        # 粘贴数据
        for i, row in enumerate(data):
            for j, value in enumerate(row):
                row_idx = start_row + i
                col_idx = start_col + j

                # 更新表格
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))

                # 更新DataFrame
                df = self.sheets_data[self.current_sheet]
                # 扩展DataFrame如果需要
                if row_idx >= len(df):
                    # 添加新行
                    new_rows = row_idx - len(df) + 1
                    new_df = pd.DataFrame([[""] * len(df.columns)] * new_rows, columns=df.columns)
                    df = pd.concat([df, new_df], ignore_index=True)
                    self.sheets_data[self.current_sheet] = df

                # 确保列数足够
                if col_idx >= len(df.columns):
                    # 添加新列
                    new_cols = col_idx - len(df.columns) + 1
                    for c in range(new_cols):
                        new_col_name = self.generate_unique_column_name(df)
                        df[new_col_name] = ["" for _ in range(len(df))]
                    self.sheets_data[self.current_sheet] = df
                    # 重新显示表格以更新列头
                    self.display_sheet(self.current_sheet)

                # 更新单元格值
                self.sheets_data[self.current_sheet].iat[row_idx, col_idx] = value

        self.status_bar.setText("已粘贴内容")

    def search_content(self, text):
        """搜索内容"""
        if not text or not self.current_sheet:
            return

        found = False
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and text.lower() in item.text().lower():
                    self.table.setCurrentCell(row, col)
                    found = True
                    break
            if found:
                break

        if not found:
            self.create_warningbar("搜索结果", "未找到匹配的内容")

    def save_file(self):
        """保存文件（修复版）"""
        if not self.current_file:
            self.save_file_as()
            return

        try:
            # 根据文件扩展名确定引擎
            if self.current_file.lower().endswith('.xlsx'):
                engine = 'openpyxl'
            else:
                engine = 'xlsxwriter'  # xlwt 不支持 .xls 写入新文件

            # 直接使用ExcelWriter覆盖保存
            with pd.ExcelWriter(self.current_file, engine=engine) as writer:
                for sheet_name, df in self.sheets_data.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            self.status_bar.setText(f"已保存文件: {os.path.basename(self.current_file)}")
            self.create_successbar("文件保存成功", f"已保存到: {os.path.basename(self.current_file)}")

        except Exception as e:
            self.create_errorbar("保存失败", f"无法保存文件: {str(e)}")

    def save_file_as(self):
        """另存为"""
        if not self.sheets_data:
            self.create_warningbar("操作失败", "没有可保存的数据")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "另存为", "", "Excel Files (*.xlsx *.xls)"
        )

        if not file_path:
            return

        # 确保文件扩展名
        if not file_path.lower().endswith(('.xlsx', '.xls')):
            file_path += '.xlsx'

        try:
            # 根据文件扩展名确定引擎
            if file_path.lower().endswith('.xlsx'):
                engine = 'openpyxl'
            else:
                engine = 'xlsxwriter'  # xlwt 不支持 .xls 写入新文件

            # 保存所有工作表
            with pd.ExcelWriter(file_path, engine=engine) as writer:
                for sheet_name, df in self.sheets_data.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            self.current_file = file_path
            self.file_path_label.setText(f"当前文件: {file_path}")

            self.status_bar.setText(f"已另存为: {os.path.basename(file_path)}")
            self.create_successbar("文件保存成功", f"已保存到: {os.path.basename(file_path)}")

        except Exception as e:
            self.create_errorbar("保存失败", f"无法保存文件: {str(e)}")

    # ===== 通知方法 =====
    def create_successbar(self, title: str, content: str = "", duration: int = 3000):
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=self
        )

    def create_errorbar(self, title: str, content: str = "", duration: int = 3000):
        logger.info(f"{title}: {content}")
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=self
        )

    def create_warningbar(self, title: str, content: str = "", duration=3000):
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=self
        )

    def create_infobar(self, title: str, content: str = "", duration=3000):
        InfoBar.info(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=self
        )


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    from qfluentwidgets import setTheme, Theme

    # 设置主题
    setTheme(Theme.AUTO)

    app = QApplication(sys.argv)
    editor = ExcelEditor()
    editor.show()
    sys.exit(app.exec_())