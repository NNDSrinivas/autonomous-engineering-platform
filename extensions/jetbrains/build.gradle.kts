plugins {
  id("org.jetbrains.intellij") version "1.17.2"
  kotlin("jvm") version "1.9.24"
}

group = "com.aep"
version = providers.gradleProperty("pluginVersion").get()

repositories { mavenCentral() }

intellij {
  version.set(providers.gradleProperty("ijVersion").get())
  plugins.set(listOf("java"))
}

dependencies {
  implementation("org.java-websocket:Java-WebSocket:1.5.6")
  implementation("com.fasterxml.jackson.core:jackson-databind:2.17.2")
  implementation("com.fasterxml.jackson.module:jackson-module-kotlin:2.17.2")
  implementation("com.squareup.okhttp3:okhttp:4.12.0")
}

tasks {
  patchPluginXml {
    sinceBuild.set(providers.gradleProperty("pluginSinceBuild").get())
    changeNotes.set("Initial IntelliJ adapter for AEP Agent.")
  }
  compileKotlin { kotlinOptions.jvmTarget = "17" }
  runIde { jvmArgs("-Xmx1g") }
}
