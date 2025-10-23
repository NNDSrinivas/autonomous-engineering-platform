package com.aep.ide

import com.aep.ide.ws.RpcClient
import com.intellij.notification.Notification
import com.intellij.notification.NotificationType
import com.intellij.notification.Notifications
import java.io.File

object AgentService {
  private var client: RpcClient? = null
  private var started: Boolean = false
  private var agentProcess: Process? = null
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
      // Use AEP_AGENT_CORE_PATH env var if set, otherwise fall back to user.dir
      val agentCorePath = System.getenv("AEP_AGENT_CORE_PATH") ?: System.getProperty("user.dir")
      val agentCore = File(agentCorePath, "agent-core")
      val pkgJson = File(agentCore, "package.json")
      if (pkgJson.exists() && !started) {
        try {
          val cmd = listOf("npm", "run", "dev:agentd")
          val pb = ProcessBuilder(cmd).directory(agentCore).redirectErrorStream(true)
          val proc = pb.start()
          agentProcess = proc
          started = true
          // Retry connection with exponential backoff (capped at 10s max)
          // Retries 0-6 use true exponential (200ms -> 12.8s capped to 10s)
          var retries = 0
          while (retries < 7) {
            Thread.sleep(minOf(200L * (1 shl retries), 10000L)) // 200ms, 400ms, ..., max 10s
            try {
              client = RpcClient(url)
              client!!.connectBlocking()
              return client!!
            } catch (_: Exception) {
              retries++
            }
          }
        } catch (e: Exception) {
          // If startup fails, attempt to read process output for diagnostics
          try {
            agentProcess?.inputStream?.bufferedReader()?.useLines { lines ->
              lines.take(50).forEach { println("agentd: $it") }
            }
          } catch (_: Exception) {
          }
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

  fun stopAgentIfStarted() {
    try {
      agentProcess?.destroy()
      agentProcess = null
    } catch (_: Exception) {
    }
  }
}
