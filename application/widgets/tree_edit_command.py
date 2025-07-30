"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: tree_edit_command.py
@time: 2025/7/4 16:23
@desc: 
"""
from PyQt5.QtWidgets import QUndoCommand


# 撤销/重做命令类
class TreeEditCommand(QUndoCommand):
    def __init__(self, editor, old_state, description):
        super().__init__(description)
        self.editor = editor
        self.old_state = old_state
        self.new_state = None

    def redo(self):
        if self.new_state:
            # 保存当前树的展开状态
            tree_state = self.editor.capture_tree_state()
            # 保存当前状态
            current_state = self.editor.capture_tree_data()
            # 应用新状态
            self.editor.reload_tree(self.new_state)
            # 恢复树的展开状态
            self.editor.restore_tree_state_only(tree_state)

        return None

    def undo(self):
        # 保存当前树的展开状态
        tree_state = self.editor.capture_tree_state()
        # 保存当前状态作为新状态（首次执行）
        if not self.new_state:
            self.new_state = self.editor.capture_tree_data()
        # 保存当前状态
        current_state = self.editor.capture_tree_data()
        # 恢复旧状态
        self.editor.reload_tree(self.old_state)
        # 恢复树的展开状态
        self.editor.restore_tree_state_only(tree_state)
        return None
