package com.quantumflex.sentinel

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Start native foreground service
        val serviceIntent = Intent(this, SentinelService::class.java)
        startForegroundService(serviceIntent)

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 64, 48, 64)
        }

        val title = TextView(this).apply {
            text = "QuantumFlex Mobile Sentinel"
            textSize = 22f
            setPadding(0, 0, 0, 24)
        }
        layout.addView(title)

        val initialized = NativeBridge.initialize()
        val version = NativeBridge.getVersion()

        // Test typed invariant states
        val testAllow = NativeBridge.checkSolvency(1000L, 500L, true)
        val testDeny = NativeBridge.checkSolvency(500L, 1000L, true)
        val testUnknown = NativeBridge.checkSolvency(1000L, 500L, false)

        val hasStrongBox = HardwareAdapter.hasStrongBox(this)
        val strongBoxKey = HardwareAdapter.verifyStrongBoxIdentityKey(this)
        val sensorInfo = HardwareAdapter.getSensorSummary(this)

        val status = TextView(this).apply {
            text = """
                • Native Rust Core: libqflex_edge.so (Loaded)
                • Core Version: $version
                • JNI Bridge Initialized: $initialized
                • Invariant Allow (1000 >= 500, valid): $testAllow
                • Invariant Deny (500 >= 1000, valid): $testDeny
                • Invariant Fail-Closed (1000 >= 500, invalid): $testUnknown
                • StrongBox HSM Available: $hasStrongBox
                • StrongBox Key Initialized: $strongBoxKey
                • Sensor Subsystem: $sensorInfo
                • Service State: Foreground Active (specialUse)
            """.trimIndent()
            textSize = 15f
            setLineSpacing(8f, 1f)
        }
        layout.addView(status)

        setContentView(layout)
    }
}
