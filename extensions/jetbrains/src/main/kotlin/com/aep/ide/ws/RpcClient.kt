package com.aep.ide.ws

import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import java.net.URI
import java.util.UUID
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.core.type.TypeReference
import com.fasterxml.jackson.module.kotlin.registerKotlinModule
import com.intellij.openapi.diagnostic.Logger

class RpcClient(url: String) : WebSocketClient(URI(url)) {
  companion object {
    private val logger = Logger.getInstance(RpcClient::class.java)
  }
  
  private val mapper = ObjectMapper().registerKotlinModule()
  private val pending = ConcurrentHashMap<String, CompletableFuture<Map<String, Any?>>>()

  override fun onOpen(handshakedata: ServerHandshake?) {}
  override fun onClose(code: Int, reason: String?, remote: Boolean) {
    logger.info("WebSocket closed: code=$code, reason=$reason, remote=$remote")
    val ex = Exception("WebSocket closed: code=$code, reason=$reason, remote=$remote")
    // Fail all pending requests
    pending.values.forEach { it.completeExceptionally(ex) }
    pending.clear()
  }
  override fun onError(ex: Exception) { logger.error("WebSocket error", ex) }

  override fun onMessage(message: String) {
    // Use TypeReference for type-safe deserialization to avoid unchecked casts
    val map: Map<String, Any?> = mapper.readValue(message, object : TypeReference<Map<String, Any?>>() {})
    val id = map["id"] as? String ?: return
    val p = pending.remove(id) ?: return
    p.complete(map)
  }

  fun call(method: String, params: Map<String, Any?> = emptyMap()): CompletableFuture<Map<String, Any?>> {
    val id = UUID.randomUUID().toString()
    val fut = CompletableFuture<Map<String, Any?>>()
    pending[id] = fut
    val payload = mapOf("id" to id, "method" to method, "params" to params)
    val json = mapper.writeValueAsString(payload)
    try {
      send(json)
      // Add timeout to prevent memory leaks from stale requests
      fut.orTimeout(30, java.util.concurrent.TimeUnit.SECONDS).whenComplete { _, ex ->
        if (ex != null) {
          pending.remove(id)
        }
      }
    } catch (ex: Exception) {
      pending.remove(id)
      fut.completeExceptionally(ex)
    }
    return fut
  }
}
