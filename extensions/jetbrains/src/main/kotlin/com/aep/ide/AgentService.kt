package com.aep.ide

import com.aep.ide.ws.RpcClient
import com.intellij.notification.Notification
import com.intellij.notification.NotificationType
import com.intellij.notification.Notifications
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import java.io.File
import org.java_websocket.client.WebSocketClient

@Service(Service.Level.APP)
class AgentService {
  companion object {
    private val logger = Logger.getInstance(AgentService::class.java)
  }
  
  private val lock = Any()
  @Volatile private var client: RpcClient? = null
  @Volatile private var started: Boolean = false
  @Volatile private var agentProcess: Process? = null
  private val url = System.getenv("AEP_AGENTD_URL") ?: "ws://127.0.0.1:8765"

  private fun calculateBackoffDelay(attempt: Int): Long {
    // Exponential backoff: 200ms * 2^attempt, capped at 10s
    // 200ms, 400ms, 800ms, 1.6s, 3.2s, 6.4s, 10s (capped)
    return minOf(200L * (1 shl attempt), 10000L)
  }

  fun ensureAgentRunning(): RpcClient = synchronized(lock) {
    client?.takeIf { it.isOpen }?.let { return it }
    // Try connect; if fails, attempt to start agentd from repo (Node script)
    try {
      val newClient = RpcClient(url)
      newClient.connectBlocking()
      client = newClient
      return newClient
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
          // Retry connection with exponential backoff (200ms -> 12.8s capped to 10s)
          // Thread.sleep is acceptable here because:
          // 1. Already executing on background thread (ApplicationManager.executeOnPooledThread)
          // 2. Only called during agent startup (not hot path)
          // 3. Synchronous return type required by callers
          for (attempt in 0..6) {
            Thread.sleep(calculateBackoffDelay(attempt))
            try {
              val newClient = RpcClient(url)
              newClient.connectBlocking()
              client = newClient
              return newClient
            } catch (_: Exception) {
              // Continue to next retry
            }
          }
        } catch (e: Exception) {
          // If startup fails, attempt to read process output for diagnostics
          try {
            agentProcess?.inputStream?.bufferedReader()?.useLines { lines ->
              lines.take(50).forEach { logger.warn("agentd: $it") }
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
      val newClient = RpcClient(url)
      newClient.connectBlocking()
      client = newClient
      return newClient
    }
  }

  fun stopAgentIfStarted() = synchronized(lock) {
    try {
      // Close WebSocket connection first
      client?.close()
      client = null
      
      // Then terminate the agent process
      agentProcess?.let { process ->
        process.destroy() // Request graceful termination
        if (!process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) {
          process.destroyForcibly() // Force kill if not stopped within 5s
        }
      }
      agentProcess = null
    } catch (_: Exception) {
    }
  }
}
