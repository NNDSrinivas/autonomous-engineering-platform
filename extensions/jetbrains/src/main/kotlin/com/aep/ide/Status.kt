package com.aep.ide

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.WindowManager

object Status {
  fun show(project: Project?, message: String, millis: Int = 8000) {
    val bar = project?.let { WindowManager.getInstance().getStatusBar(it) } ?: return
    bar.info = message
    // IntelliJ auto-clears after a bit; no timer needed for basic use
  }
}
