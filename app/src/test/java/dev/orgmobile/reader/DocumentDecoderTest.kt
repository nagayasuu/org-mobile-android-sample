package dev.orgmobile.reader

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.nio.charset.CharacterCodingException

class DocumentDecoderTest {
    @Test fun `reads Japanese UTF-8 content from a stream`() {
        val stream = "\uFEFF* 日本語\r\n- 牛乳".byteInputStream(Charsets.UTF_8)
        assertEquals(listOf(OrgBlock.Heading(1, "日本語"), OrgBlock.ListItem(0, "-", "牛乳")),
            DocumentDecoder.read(stream))
    }

    @Test fun `rejects malformed UTF-8 instead of silently corrupting Japanese`() {
        val stream = byteArrayOf(0xC3.toByte(), 0x28).inputStream()
        assertThrows(CharacterCodingException::class.java) { DocumentDecoder.read(stream) }
    }
}
