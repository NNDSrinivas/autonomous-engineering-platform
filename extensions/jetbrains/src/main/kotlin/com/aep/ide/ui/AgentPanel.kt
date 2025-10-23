package com.aep.ide.ui

import com.aep.ide.AgentService
import com.aep.ide.Status
import com.fasterxml.jackson.core.type.TypeReference
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.registerKotlinModule
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.service
import com.intellij.openapi.project.Project
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.awt.BorderLayout
import java.util.concurrent.TimeUnit
import java.util.Locale
import javax.swing.*
import javax.swing.border.EmptyBorder

class AgentPanel(private val project: Project) : JPanel(BorderLayout()) {
  companion object {
    private val http = OkHttpClient.Builder()
      .connectTimeout(10, TimeUnit.SECONDS)
      .readTimeout(30, TimeUnit.SECONDS)
      .writeTimeout(30, TimeUnit.SECONDS)
      .build()
    
    // Regex patterns for telemetry parsing (compiled once for performance)
    private val SANITIZE_PATTERN = Regex("[,\$\\s]")
    private val LONG_VALIDATION_PATTERN = Regex("""^-?\d+$""")
    private val DOUBLE_VALIDATION_PATTERN = Regex("""^-?\d+(\.\d+)?$""")
    
    /**
     * Safely parse a Long value from telemetry map, handling Number types and sanitized string formats.
     * Accepts strings with commas, dollar signs, or whitespace (e.g., "1,234" or "$123").
     */
    private fun parseLongFromTelemetry(value: Any?): Long {
      return (value as? Number)?.toLong()
        ?: value?.toString()?.trim()?.replace(SANITIZE_PATTERN, "")?.let { s ->
          if (LONG_VALIDATION_PATTERN.matches(s)) s.toLongOrNull() else null
        }
        ?: 0L
    }
    
    /**
     * Safely parse a Double value from telemetry map, handling Number types and sanitized string formats.
     * Accepts strings with commas, dollar signs, or whitespace (e.g., "$12.34" or "1,234.56").
     */
    private fun parseDoubleFromTelemetry(value: Any?): Double {
      return (value as? Number)?.toDouble()
        ?: value?.toString()?.trim()?.replace(SANITIZE_PATTERN, "")?.let { s ->
          if (DOUBLE_VALIDATION_PATTERN.matches(s)) s.toDoubleOrNull() else null
        }
        ?: 0.0
    }
  }

  private val out = JTextArea()
  private val mapper = ObjectMapper().registerKotlinModule()
  private val JSON = "application/json; charset=utf-8".toMediaType()
  private val coreApi = System.getenv("AEP_CORE_API") ?: "http://localhost:8002"

  init {
    border = EmptyBorder(8, 8, 8, 8)

    val btnOpen = JButton("Open Session")
    val btnPlanLLM = JButton("Generate Plan (LLM)")
    val btnApprove = JButton("Approve & Run")
    val btnDraftPR = JButton("Draft PR")
    val btnJira = JButton("JIRA Comment")

    val top = JPanel().apply {
      layout = BoxLayout(this, BoxLayout.X_AXIS)
      add(btnOpen)
      add(Box.createHorizontalStrut(8))
      add(btnPlanLLM)
      add(Box.createHorizontalStrut(8))
      add(btnApprove)
      add(Box.createHorizontalStrut(8))
      add(btnDraftPR)
      add(Box.createHorizontalStrut(8))
      add(btnJira)
    }
    add(top, BorderLayout.NORTH)
    add(JScrollPane(out), BorderLayout.CENTER)

    // --- Open session (via agentd) ---
    btnOpen.addActionListener {
      btnOpen.isEnabled = false
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val c = service<AgentService>().ensureAgentRunning()
          c.call("session.open").whenComplete { res, err ->
            SwingUtilities.invokeLater {
              btnOpen.isEnabled = true
              if (err != null) {
                append("ERROR opening session: ${err.message}\n")
              } else {
                append("Greeting:\n${pretty(res)}\n")
              }
            }
          }
        } catch (e: Exception) {
          SwingUtilities.invokeLater {
            btnOpen.isEnabled = true
            append("ERROR opening session: ${e.message}\n")
          }
        }
      }
    }

    // --- Generate Plan (LLM) -> backend /api/context + /api/plan ---
    btnPlanLLM.addActionListener {
      val key = JOptionPane.showInputDialog(this, "Ticket key:", "AEP-27") ?: return@addActionListener
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          // 1) fetch context pack
          val ctxReq = Request.Builder()
            .url("$coreApi/api/context/task/$key")
            .get()
            .build()
          http.newCall(ctxReq).execute().use { resp ->
            if (!resp.isSuccessful) throw RuntimeException("Context HTTP ${resp.code}")
            val contextBody = resp.body?.string() ?: throw RuntimeException("Empty context response body")
            val contextPack = mapper.readValue(contextBody, object : TypeReference<Map<String, Any?>>() {})

            // 2) call plan API
            val bodyMap = mapOf("contextPack" to contextPack)
            val planReq = Request.Builder()
              .url("$coreApi/api/plan/$key")
              .post(mapper.writeValueAsString(bodyMap).toRequestBody(JSON))
              .addHeader("X-Org-Id", "default")
              .build()
            http.newCall(planReq).execute().use { presp ->
              if (!presp.isSuccessful) throw RuntimeException("Plan HTTP ${presp.code}")
              val planBody = presp.body?.string() ?: throw RuntimeException("Empty plan response body")
              val planRes = mapper.readValue(planBody, object : TypeReference<Map<String, Any?>>() {})
              append("LLM Plan:\n${pretty(planRes)}\n")

              // status bar telemetry
              val t = (planRes["telemetry"] as? Map<*, *>) ?: emptyMap<Any, Any>()
              val model = t["model"]?.toString() ?: "n/a"
              
              // Parse numeric telemetry values using helper functions
              val tokens = parseLongFromTelemetry(t["tokens"])
              val cost = String.format(Locale.US, "$%.2f", parseDoubleFromTelemetry(t["cost_usd"]))
              val latency = parseLongFromTelemetry(t["latency_ms"])
              
              Status.show(project, "AEP Plan — model: $model | tokens: $tokens | cost: $cost | latency: ${latency}ms")
            }
          }
        } catch (e: Exception) {
          append("ERROR generating plan: ${e.message}\n")
          Status.show(project, "AEP Plan error: ${e.message}", 8000)
        }
      }
    }

    // --- Approve & Run (via agentd) ---
    btnApprove.addActionListener {
      val planJson = JOptionPane.showInputDialog(this, "Paste plan JSON.items to execute (array):", "[]") ?: return@addActionListener
      val items: List<Map<String, Any?>>
      try {
        items = mapper.readValue(planJson, object : TypeReference<List<Map<String, Any?>>>() {})
      } catch (e: Exception) {
        append("Invalid JSON: ${e.message}\n")
        JOptionPane.showMessageDialog(this, "Invalid JSON: ${e.message}", "JSON Parse Error", JOptionPane.ERROR_MESSAGE)
        return@addActionListener
      }
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val c = service<AgentService>().ensureAgentRunning()
          for (step in items) {
            // Sanitize step data for display
            val kind = (step["kind"] as? String)?.take(50) ?: "unknown"
            val desc = (step["desc"] as? String)?.take(200) ?: "no description"
            val stepId = (step["id"] as? String)?.take(50) ?: "unknown"
            
            var approve = JOptionPane.CANCEL_OPTION
            SwingUtilities.invokeAndWait {
              approve = JOptionPane.showConfirmDialog(this, "Run step: $kind - $desc ?", "Confirm", JOptionPane.OK_CANCEL_OPTION)
            }
            if (approve != JOptionPane.OK_OPTION) {
              append("Cancelled: $stepId - stopping execution\n")
              break
            }
            val res = c.call("plan.runStep", mapOf("step" to step)).get()
            append("Step $stepId -> ${pretty(res)}\n")
          }
        } catch (e: Exception) {
          append("Error in Approve & Run: ${e.message}\n")
        }
      }
    }

    // --- Draft PR (OkHttp) ---
    btnDraftPR.addActionListener {
      val repo = JOptionPane.showInputDialog(this, "repo (org/repo):") ?: return@addActionListener
      val base = JOptionPane.showInputDialog(this, "base branch:", "main") ?: return@addActionListener
      val head = JOptionPane.showInputDialog(this, "head branch:", "feat/sample") ?: return@addActionListener
      val title = JOptionPane.showInputDialog(this, "PR title:") ?: return@addActionListener
      val body = JOptionPane.showInputDialog(this, "PR body:", "Implements ...") ?: ""
      val ticket = JOptionPane.showInputDialog(this, "Ticket key (optional):", "") ?: ""
      val payload = mapper.writeValueAsString(mapOf(
        "repo_full_name" to repo, "base" to base, "head" to head,
        "title" to title, "body" to body, "ticket_key" to ticket, "dry_run" to false
      ))
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val req = Request.Builder()
            .url("$coreApi/api/deliver/github/draft-pr")
            .post(payload.toRequestBody(JSON))
            .addHeader("Content-Type", "application/json")
            .addHeader("X-Org-Id", "default")
            .build()
          http.newCall(req).execute().use { resp ->
            val text = resp.body?.string() ?: ""
            append("Draft PR response (${resp.code}): $text\n")
            Status.show(project, if (resp.isSuccessful) "Draft PR created" else "Draft PR failed: ${resp.code}")
          }
        } catch (e: Exception) {
          append("Draft PR error: ${e.message}\n")
          Status.show(project, "Draft PR error: ${e.message}")
        }
      }
    }

    // --- JIRA Comment (OkHttp) ---
    btnJira.addActionListener {
      val issue = JOptionPane.showInputDialog(this, "Issue key:", "AEP-27") ?: return@addActionListener
      val comment = JOptionPane.showInputDialog(this, "Comment:", "Shipping PR soon") ?: return@addActionListener
      val transition = JOptionPane.showInputDialog(this, "Transition (optional):", "") ?: ""
      val payload = mapper.writeValueAsString(mapOf(
        "issue_key" to issue, "comment" to comment,
        "transition" to (if (transition.isBlank()) null else transition), "dry_run" to false
      ))
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val req = Request.Builder()
            .url("$coreApi/api/deliver/jira/comment")
            .post(payload.toRequestBody(JSON))
            .addHeader("Content-Type", "application/json")
            .addHeader("X-Org-Id", "default")
            .build()
          http.newCall(req).execute().use { resp ->
            val text = resp.body?.string() ?: ""
            append("JIRA response (${resp.code}): $text\n")
            Status.show(project, if (resp.isSuccessful) "JIRA comment posted" else "JIRA comment failed: ${resp.code}")
          }
        } catch (e: Exception) {
          append("JIRA comment error: ${e.message}\n")
          Status.show(project, "JIRA error: ${e.message}")
        }
      }
    }
  }

  private fun append(s: String) { 
    SwingUtilities.invokeLater { 
      out.append(s)
    }
  }
  
  private fun pretty(map: Any?): String = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(map)
}
