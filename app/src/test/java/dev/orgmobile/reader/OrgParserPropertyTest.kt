package dev.orgmobile.reader

import io.kotest.property.Arb
import io.kotest.property.arbitrary.element
import io.kotest.property.arbitrary.int
import io.kotest.property.checkAll
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

class OrgParserPropertyTest {
    @Test fun `heading depth and Unicode title are preserved`() = runTest {
        checkAll(PropertyInputs.config("headings"), Arb.int(1..64), PropertyInputs.line) { depth, text ->
            val title = "題:$text"
            assertEquals(listOf(OrgBlock.Heading(depth, title)),
                OrgParser.parse("${"*".repeat(depth)} $title"))
        }
    }

    @Test fun `list marker content and mixed indentation are preserved`() = runTest {
        checkAll(PropertyInputs.config("lists"), PropertyInputs.indent,
            PropertyInputs.marker, PropertyInputs.line) { whitespace, marker, text ->
            val prefix = whitespace.joinToString("").let {
                if (marker == "*" && it.isEmpty()) " " else it
            }
            val indent = prefix.count { it == ' ' } + 4 * prefix.count { it == '\t' }
            val body = "項目:$text"
            for (separator in listOf(" ", "\t", " \t")) {
                assertEquals(listOf(OrgBlock.ListItem(indent, marker, body)),
                    OrgParser.parse("$prefix$marker$separator$body"))
            }
        }
    }

    @Test fun `CRLF and leading BOM preserve the LF document result`() = runTest {
        checkAll(PropertyInputs.config("newlines"), PropertyInputs.document) { document ->
            val expected = OrgParser.parse(document)
            val crlf = document.replace("\n", "\r\n")
            for (variant in listOf(crlf, "\uFEFF$document", "\uFEFF$crlf")) {
                assertEquals(expected, OrgParser.parse(variant))
            }
        }
    }

    @Test fun `literal blocks preserve syntax and resume after the matching end`() = runTest {
        checkAll(PropertyInputs.config("literal blocks"),
            Arb.element(listOf("src", "EXAMPLE", "QuOtE")), PropertyInputs.line) { name, text ->
            val literal = "#+BeGiN_$name\n* 題:$text\n\n\t- 項目:$text\n#+end_other\n#+EnD_$name"
            assertEquals(listOf(OrgBlock.Paragraph(literal), OrgBlock.Heading(2, "続き:$text")),
                OrgParser.parse("$literal\n** 続き:$text"))
        }
    }

    @Test fun `separate parses do not share paragraph or literal block state`() = runTest {
        checkAll(PropertyInputs.config("independent parses"), PropertyInputs.line,
            PropertyInputs.line, Arb.int(0..2)) { first, second, kind ->
            val a = when (kind) {
                0 -> ""
                1 -> "本文:$first"
                else -> "#+BEGIN_SRC\n* $first\n"
            }
            val expectedA = if (kind == 0) emptyList() else listOf(OrgBlock.Paragraph(a))
            val b = "* 題:$second\n本文:$second"
            val expectedB = listOf(OrgBlock.Heading(1, "題:$second"), OrgBlock.Paragraph("本文:$second"))
            assertEquals(expectedA, OrgParser.parse(a))
            assertEquals(expectedB, OrgParser.parse(b))
            assertEquals(expectedA, OrgParser.parse(a))
        }
    }
}
