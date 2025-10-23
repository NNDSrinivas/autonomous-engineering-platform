package com.aep.ide

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.WindowManager

/**
 * Utility for displaying messages in IntelliJ's status bar.
 */
object Status {
  /**
   * Shows a message in the status bar.
   * 
   * @param project The project instance
   * @param message The message to display
   * @param millis The intended duration to show the message (in milliseconds). Currently unused,
   *               as IntelliJ auto-clears the status bar after a short period. This parameter is
   *               retained for future extensibility or compatibility with other APIs.
   */
  fun show(project: Project?, message: String, millis: Int = 8000) {
    val bar = project?.let { WindowManager.getInstance().getStatusBar(it) } ?: return
    bar.info = message
    // IntelliJ auto-clears after a bit; no timer needed for basic use
  }
}
