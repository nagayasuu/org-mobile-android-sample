package dev.orgmobile.reader

import io.kotest.property.Arb
import io.kotest.property.PropTestConfig
import io.kotest.property.arbitrary.bind
import io.kotest.property.arbitrary.choice
import io.kotest.property.arbitrary.element
import io.kotest.property.arbitrary.int
import io.kotest.property.arbitrary.list
import io.kotest.property.arbitrary.map
import kotlin.random.Random

/** Public synthetic inputs only. No lone surrogates, BOM, or line separators in a line. */
internal object PropertyInputs {
    private val scalar = Arb.int(0..0x10F7FF).map {
        val codePoint = if (it >= 0xD800) it + 0x800 else it
        when (codePoint) {
            10, 13, 0x85, 0x2028, 0x2029, 0xFEFF -> "文"
            else -> String(Character.toChars(codePoint))
        }
    }
    private val character = Arb.choice(
        Arb.element(listOf("あ", "漢", "😀", " ", "\t", "*", "+", "-", "#", "\u0000")),
        scalar,
    )
    val line = Arb.list(character, 0..64).map { it.joinToString("") }
    val indent = Arb.list(Arb.element(listOf(" ", "\t")), 0..16)
    val marker = Arb.choice(
        Arb.element(listOf("-", "+", "*")),
        Arb.bind(Arb.int(0..9999), Arb.element(listOf(".", ")"))) { n, end -> "$n$end" },
    )
    val document = Arb.list(
        Arb.bind(Arb.int(0..5), line) { kind, text ->
            when (kind) {
                0 -> ""
                1 -> "* 題:$text"
                2 -> "\t- 項目:$text"
                3 -> "#+TITLE: $text"
                4 -> "#+BEGIN_EXAMPLE\n* $text\n#+END_EXAMPLE"
                else -> "本文:$text"
            }
        },
        0..24,
    ).map { it.joinToString("\n") }

    @OptIn(io.kotest.common.ExperimentalKotest::class)
    fun config(property: String): PropTestConfig {
        val seed = System.getProperty("orgmobile.property.seed")?.toLong() ?: Random.nextLong()
        println("Property=$property Kotest=6.2.6 iterations=1000 seed=$seed")
        return PropTestConfig(iterations = 1_000, seed = seed, maxFailure = 0)
    }
}
