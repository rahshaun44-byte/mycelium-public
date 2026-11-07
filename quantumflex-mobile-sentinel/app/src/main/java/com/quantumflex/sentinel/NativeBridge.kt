package com.quantumflex.sentinel

enum class InvariantDecision(val code: Int) {
    ALLOW(1),
    DENY(2),
    UNKNOWN(3);

    companion object {
        fun fromCode(code: Int): InvariantDecision = when (code) {
            1 -> ALLOW
            2 -> DENY
            else -> UNKNOWN
        }
    }
}

object NativeBridge {

    init {
        System.loadLibrary("qflex_edge")
    }

    external fun initialize(): Boolean

    external fun getVersion(): String

    external fun evaluateSolvency(
        resources: Long,
        obligations: Long,
        measurementValid: Boolean
    ): Int

    fun checkSolvency(
        resources: Long,
        obligations: Long,
        measurementValid: Boolean = true
    ): InvariantDecision {
        val code = evaluateSolvency(resources, obligations, measurementValid)
        return InvariantDecision.fromCode(code)
    }

    external fun shutdown()
}
