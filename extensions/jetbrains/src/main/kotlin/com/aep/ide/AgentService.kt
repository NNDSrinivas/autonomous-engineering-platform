package com.aep.ide

import com.aep.ide.ws.RpcClient
import com.intellij.notification.Notification
import com.intellij.notification.NotificationType
import com.intellij.notification.Notifications
import java.io.File

object AgentService {
  private var client: RpcClient? = null
  private var started: Boolean = false
  private val url = System.getenv("AEP_AGENTD_URL") ?: "ws://127.0.0.1:8765"

  fun ensureAgentRunning(): RpcClient {
    if (client != null && client!!.isOpen) return client!!
    // Try connect; if fails, attempt to start agentd from repo (Node script)
    try {
      client = RpcClient(url)
      client!!.connectBlocking()
      return client!!
    } catch (_: Exception) {
      // Attempt to start: agent-core dev script (user must have Node installed)
      val repoHome = System.getProperty("user.dir")
      val agentCore = File(repoHome, "agent-core")
      val pkgJson = File(agentCore, "package.json")
      if (pkgJson.exists() && !started) {
        try {
          val cmd = listOf("npm", "run", "dev:agentd")
          val pb = ProcessBuilder(cmd).directory(agentCore).redirectErrorStream(true)
          pb.start()
          started = true
          // Retry connection with exponential backoff
          var retries = 0
          while (retries < 10) {
            Thread.sleep(200L * (1 shl retries)) // 200ms, 400ms, 800ms, etc.
            try {
              client = RpcClient(url)
              client!!.connectBlocking()
              return client!!
            } catch (_: Exception) {
              retries++
            }
          }
        } catch (e: Exception) {
          Notifications.Bus.notify(
            Notification(
              "AEP",
              "AEP Agent",
              "Failed to start aep-agentd: ${e.message}",
              NotificationType.WARNING
            )
          )
        }
      }
      client = RpcClient(url)
      client!!.connectBlocking()
      return client!!
    }
  }
}
