package dev.orgmobile.reader

import io.kotest.property.Arb
import io.kotest.property.arbitrary.element
import io.kotest.property.checkAll
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.nio.charset.CharacterCodingException

class DocumentDecoderPropertyTest {
    @Test fun `UTF-8 preserves Unicode content and rejects malformed sequences`() = runTest {
        val malformed = Arb.element(listOf(
            listOf(0x80), listOf(0xC0, 0xAF), listOf(0xC3, 0x28),
            listOf(0xE2, 0x82), listOf(0xED, 0xA0, 0x80), listOf(0xF4, 0x90, 0x80, 0x80),
        ))
        checkAll(PropertyInputs.config("UTF-8"), PropertyInputs.document,
            PropertyInputs.line, malformed) { document, text, invalid ->
            for (source in listOf(document, "\uFEFF" + document.replace("\n", "\r\n"))) {
                source.byteInputStream(Charsets.UTF_8).use {
                    assertEquals(OrgParser.parse(source), DocumentDecoder.read(it))
                }
            }
            val body = "本文:$text"
            body.byteInputStream(Charsets.UTF_8).use {
                assertEquals(listOf(OrgBlock.Paragraph(body)), DocumentDecoder.read(it))
            }
            val bytes = body.toByteArray(Charsets.UTF_8) + invalid.map { it.toByte() }.toByteArray()
            bytes.inputStream().use {
                assertThrows(CharacterCodingException::class.java) { DocumentDecoder.read(it) }
            }
        }
    }
}
