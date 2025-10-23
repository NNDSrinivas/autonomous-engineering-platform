package com.aep.ide.ui

import com.aep.ide.AgentService
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.registerKotlinModule
import com.intellij.openapi.application.ApplicationManager
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.awt.BorderLayout
import javax.swing.*
import javax.swing.border.EmptyBorder

class AgentPanel : JPanel(BorderLayout()) {
  private val out = JTextArea()
  private val mapper = ObjectMapper().registerKotlinModule()
  private val http = OkHttpClient()

  init {
    border = EmptyBorder(8, 8, 8, 8)
    val btnOpen = JButton("Open Session")
    val btnPlan = JButton("Generate Plan (LLM)")
    val btnApprove = JButton("Approve & Run")
    val btnDraftPR = JButton("Draft PR")
    val btnJira = JButton("JIRA Comment")

    val top = JPanel().apply {
      layout = BoxLayout(this, BoxLayout.X_AXIS)
      add(btnOpen)
      add(Box.createHorizontalStrut(8))
      add(btnPlan)
      add(Box.createHorizontalStrut(8))
      add(btnApprove)
      add(Box.createHorizontalStrut(8))
      add(btnDraftPR)
      add(Box.createHorizontalStrut(8))
      add(btnJira)
    }

    add(top, BorderLayout.NORTH)
    add(JScrollPane(out), BorderLayout.CENTER)

    btnOpen.addActionListener {
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val c = AgentService.ensureAgentRunning()
          c.call("session.open").thenAccept { res -> append("Greeting:\n${pretty(res)}\n") }
        } catch (e: Exception) {
          append("Error: ${e.message}\n")
        }
      }
    }

    btnPlan.addActionListener {
      val key =
        JOptionPane.showInputDialog(this, "Ticket key:", "AEP-27") ?: return@addActionListener
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val c = AgentService.ensureAgentRunning()
          c.call("ticket.select", mapOf("key" to key)).thenAccept { _ ->
            c.call("plan.propose", mapOf("key" to key)).thenAccept { plan ->
              append("Plan Proposed:\n${pretty(plan)}\n")
            }
          }
        } catch (e: Exception) {
          append("Error: ${e.message}\n")
        }
      }
    }

    btnApprove.addActionListener {
      val planJson =
        JOptionPane.showInputDialog(this, "Paste plan JSON.items to execute (array):", "[]")
          ?: return@addActionListener
      // Use TypeReference for safer deserialization of plan items
      val items: List<Map<String, Any?>> =
        mapper.readValue(planJson, object : com.fasterxml.jackson.core.type.TypeReference<List<Map<String, Any?>>>() {})
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val c = AgentService.ensureAgentRunning()
          items.forEach { step ->
            var approve = JOptionPane.CANCEL_OPTION
            SwingUtilities.invokeAndWait {
              approve =
                JOptionPane.showConfirmDialog(
                  this,
                  "Run step: ${step["kind"]} - ${step["desc"]} ?",
                  "Confirm",
                  JOptionPane.OK_CANCEL_OPTION
                )
            }
            if (approve != JOptionPane.OK_OPTION) {
              append("Cancelled: ${step["id"]}\n")
              return@forEach
            }
            val res = c.call("plan.runStep", mapOf("step" to step)).get()
            append("Step ${step["id"]} -> ${pretty(res)}\n")
          }
        } catch (e: Exception) {
          append("Error: ${e.message}\n")
        }
      }
    }

    btnDraftPR.addActionListener {
      val repo = JOptionPane.showInputDialog(this, "repo (org/repo):") ?: return@addActionListener
      val base = JOptionPane.showInputDialog(this, "base branch:", "main") ?: return@addActionListener
      val head =
        JOptionPane.showInputDialog(this, "head branch:", "feat/sample") ?: return@addActionListener
      val title = JOptionPane.showInputDialog(this, "PR title:") ?: return@addActionListener
      val body = JOptionPane.showInputDialog(this, "PR body:", "Implements ...") ?: ""
      val ticket = JOptionPane.showInputDialog(this, "Ticket key (optional):", "") ?: ""
      val url = System.getenv("AEP_CORE_API") ?: "http://localhost:8002"
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val payload =
            mapper.writeValueAsString(
              mapOf(
                "repo_full_name" to repo,
                "base" to base,
                "head" to head,
                "title" to title,
                "body" to body,
                "ticket_key" to ticket,
                "dry_run" to false
              )
            )
          val req =
            Request.Builder()
              .url("$url/api/deliver/github/draft-pr")
              .addHeader("Content-Type", "application/json")
              .addHeader("X-Org-Id", "default")
              .post(payload.toRequestBody("application/json".toMediaType()))
              .build()
          val resp = http.newCall(req).execute()
          val bodyString = resp.body?.string()
          if (resp.isSuccessful) {
            append("Draft PR response: ${bodyString}\n")
          } else {
            append("Draft PR failed: ${resp.code} - ${bodyString}\n")
          }
        } catch (e: Exception) {
          append("Error: ${e.message}\n")
        }
      }
    }

    btnJira.addActionListener {
      val issue = JOptionPane.showInputDialog(this, "Issue key:", "AEP-27") ?: return@addActionListener
      val comment =
        JOptionPane.showInputDialog(this, "Comment:", "Shipping PR soon") ?: return@addActionListener
      val transition = JOptionPane.showInputDialog(this, "Transition (optional):", "") ?: ""
      val url = System.getenv("AEP_CORE_API") ?: "http://localhost:8002"
      ApplicationManager.getApplication().executeOnPooledThread {
        try {
          val payload =
            mapper.writeValueAsString(
              mapOf(
                "issue_key" to issue,
                "comment" to comment,
                "transition" to (if (transition.isBlank()) null else transition),
                "dry_run" to false
              )
            )
          val req =
            Request.Builder()
              .url("$url/api/deliver/jira/comment")
              .addHeader("Content-Type", "application/json")
              .addHeader("X-Org-Id", "default")
              .post(payload.toRequestBody("application/json".toMediaType()))
              .build()
          val resp = http.newCall(req).execute()
          val bodyString = resp.body?.string()
          if (resp.isSuccessful) {
            append("JIRA response: ${bodyString}\n")
          } else {
            append("JIRA request failed: ${resp.code} - ${bodyString}\n")
          }
        } catch (e: Exception) {
          append("Error: ${e.message}\n")
        }
      }
    }
  }

  private fun append(s: String) {
    SwingUtilities.invokeLater { out.insert("$s\n", 0) }
  }

  private fun pretty(map: Any?): String =
    mapper.writerWithDefaultPrettyPrinter().writeValueAsString(map)
}
