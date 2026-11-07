package com.quantumflex.sentinel

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log

class SentinelService : Service() {

    companion object {
        const val TAG = "QuantumFlexSentinel"
        const val CHANNEL = "qflex_sentinel"
        const val NOTIFICATION_ID = 1001
    }

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "Initializing SentinelService...")

        createNotificationChannel()

        val notification = Notification.Builder(this, CHANNEL)
            .setContentTitle("QuantumFlex Edge Sentinel")
            .setContentText("Policy engine operational [R >= O, Fail-Closed]")
            .setSmallIcon(android.R.drawable.ic_lock_lock)
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        val initialized = NativeBridge.initialize()
        val version = NativeBridge.getVersion()
        Log.i(TAG, "NativeBridge initialized: $initialized, Version: $version")

        // Perform self-test of the typed solvency invariant
        val allowRes = NativeBridge.checkSolvency(1000L, 500L, true)
        val denyRes = NativeBridge.checkSolvency(500L, 1000L, true)
        val unknownRes = NativeBridge.checkSolvency(1000L, 500L, false)
        Log.i(TAG, "Solvency self-test: allow(1000 >= 500, valid)=$allowRes")
        Log.i(TAG, "Solvency self-test: deny(500 >= 1000, valid)=$denyRes")
        Log.i(TAG, "Solvency self-test: unknown(1000 >= 500, invalid)=$unknownRes")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "SentinelService active (START_STICKY)")
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL,
            "QuantumFlex Sentinel",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "QuantumFlex Sovereign Invariant & Edge Sentinel"
        }

        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    override fun onDestroy() {
        Log.i(TAG, "Shutting down SentinelService...")
        NativeBridge.shutdown()
        super.onDestroy()
    }
}
