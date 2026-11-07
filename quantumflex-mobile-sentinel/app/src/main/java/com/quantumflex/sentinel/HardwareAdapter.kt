package com.quantumflex.sentinel

import android.content.Context
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorManager
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Log
import java.security.KeyPairGenerator
import java.security.KeyStore

object HardwareAdapter {
    private const val TAG = "QuantumFlexHW"

    fun hasStrongBox(context: Context): Boolean {
        return context.packageManager.hasSystemFeature(PackageManager.FEATURE_STRONGBOX_KEYSTORE)
    }

    fun getSensorSummary(context: Context): String {
        val sm = context.getSystemService(Context.SENSOR_SERVICE) as? SensorManager ?: return "No SensorManager"
        val sensorList = sm.getSensorList(Sensor.TYPE_ALL)
        return "Sensors detected: ${sensorList.size}"
    }

    fun verifyStrongBoxIdentityKey(context: Context): Boolean {
        if (!hasStrongBox(context)) {
            Log.w(TAG, "StrongBox not reported by system features")
            return false
        }
        return try {
            val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            val alias = "qflex_edge_identity"
            if (!keyStore.containsAlias(alias)) {
                val kpg = KeyPairGenerator.getInstance(
                    KeyProperties.KEY_ALGORITHM_EC,
                    "AndroidKeyStore"
                )
                val spec = KeyGenParameterSpec.Builder(
                    alias,
                    KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
                )
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .setIsStrongBoxBacked(true)
                    .build()
                kpg.initialize(spec)
                kpg.generateKeyPair()
                Log.i(TAG, "Generated StrongBox-backed EC identity key: $alias")
            }
            true
        } catch (e: Exception) {
            Log.w(TAG, "StrongBox key initialization note: ${e.message}")
            false
        }
    }
}

