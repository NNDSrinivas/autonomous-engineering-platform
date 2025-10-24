package com.aep.ide

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.wm.ToolWindowManager

class Actions {
  class OpenTool : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
      val project = e.project ?: return
      val tw = ToolWindowManager.getInstance(project).getToolWindow("AEP Agent") ?: return
      tw.show()
    }
  }
}
