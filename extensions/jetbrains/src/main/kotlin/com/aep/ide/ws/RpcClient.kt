package com.aep.ide.ws

import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import java.net.URI
import java.util.UUID
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.registerKotlinModule

class RpcClient(url: String) : WebSocketClient(URI(url)) {
  private val mapper = ObjectMapper().registerKotlinModule()
  private val pending = ConcurrentHashMap<String, CompletableFuture<Map<String, Any?>>>()

  override fun onOpen(handshakedata: ServerHandshake?) {}
  override fun onClose(code: Int, reason: String?, remote: Boolean) {}
  override fun onError(ex: Exception) { ex.printStackTrace() }

  override fun onMessage(message: String) {
    val map: Map<String, Any?> = mapper.readValue(message, Map::class.java) as Map<String, Any?>
    val id = map["id"] as? String ?: return
    val p = pending.remove(id) ?: return
    p.complete(map)
  }

  fun call(method: String, params: Map<String, Any?> = emptyMap()): CompletableFuture<Map<String, Any?>> {
    val id = UUID.randomUUID().toString()
    val fut = CompletableFuture<Map<String, Any?>>()
    pending[id] = fut
    val payload = mapOf("id" to id, "method" to method, "params" to params)
    val json = ObjectMapper().registerKotlinModule().writeValueAsString(payload)
    send(json)
    return fut
  }
}
