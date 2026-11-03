package dev.orgmobile.reader

import org.junit.Assert.assertEquals
import org.junit.Test

class OrgParserTest {
    @Test fun `flushes prose before a heading or list without a blank line`() {
        assertEquals(listOf(
            OrgBlock.Paragraph("前の本文"),
            OrgBlock.Heading(2, "見出し"),
            OrgBlock.Paragraph("次の本文"),
            OrgBlock.ListItem(0, "-", "項目"),
        ), OrgParser.parse("前の本文\n** 見出し\n次の本文\n- 項目"))
    }

    @Test fun `ends a literal paragraph before following prose without a blank line`() {
        val literal = "#+BEGIN_EXAMPLE\n* リテラル\n#+END_EXAMPLE"
        assertEquals(listOf(OrgBlock.Paragraph(literal), OrgBlock.Paragraph("後の本文")),
            OrgParser.parse("$literal\n後の本文"))
    }

    @Test fun `preserves an unindented star with no heading text as prose`() {
        assertEquals(listOf(OrgBlock.Paragraph("* \n*\t")), OrgParser.parse("* \n*\t"))
    }

    @Test fun `renders Japanese headings paragraphs and lists in order`() {
        val source = """
            * 買い物
            今日のメモ。
            続きの行。

            - 牛乳
            + パン
            ** 明日の予定
            1. 散歩
            2) 読書
        """.trimIndent()

        val blocks = OrgParser.parse(source)

        assertEquals(listOf(
            OrgBlock.Heading(1, "買い物"),
            OrgBlock.Paragraph("今日のメモ。\n続きの行。"),
            OrgBlock.ListItem(0, "-", "牛乳"),
            OrgBlock.ListItem(0, "+", "パン"),
            OrgBlock.Heading(2, "明日の予定"),
            OrgBlock.ListItem(0, "1.", "散歩"),
            OrgBlock.ListItem(0, "2)", "読書"),
        ), blocks)
    }

    @Test fun `keeps blank separated paragraphs distinct`() {
        assertEquals(listOf(OrgBlock.Paragraph("前半"), OrgBlock.Paragraph("後半")),
            OrgParser.parse("前半\n\n\n後半"))
    }

    @Test fun `supports nested bullets including indented stars`() {
        assertEquals(listOf(
            OrgBlock.ListItem(0, "-", "親"),
            OrgBlock.ListItem(2, "*", "子"),
            OrgBlock.ListItem(4, "+", "孫"),
        ), OrgParser.parse("- 親\n  * 子\n    + 孫"))
    }

    @Test fun `handles BOM CRLF and empty input`() {
        assertEquals(listOf(OrgBlock.Heading(1, "日本語"), OrgBlock.Paragraph("本文")),
            OrgParser.parse("\uFEFF* 日本語\r\n本文\r\n"))
        assertEquals(emptyList<OrgBlock>(), OrgParser.parse(" \n\t\n"))
    }

    @Test fun `preserves unsupported syntax as plain text`() {
        val text = "#+TITLE: メモ\n*not a heading\n[[https://example.com][リンク]]"
        assertEquals(listOf(OrgBlock.Paragraph(text)), OrgParser.parse(text))
    }

    @Test fun `does not mistake source block contents for headings or lists`() {
        val block = "#+BEGIN_SRC text\n* literal\n- literal\n#+END_SRC"
        assertEquals(listOf(OrgBlock.Paragraph(block), OrgBlock.Heading(1, "見出し")),
            OrgParser.parse("$block\n* 見出し"))
    }

    @Test fun `preserves the end of a long document`() {
        val source = (1..10_000).joinToString("\n") { "- 項目 $it" }
        val blocks = OrgParser.parse(source)
        assertEquals(10_000, blocks.size)
        assertEquals(OrgBlock.ListItem(0, "-", "項目 10000"), blocks.last())
    }

    @Test fun `literal blocks preserve blank lines and resume parsing after mixed case end`() {
        val literal = "#+begin_src text\n* literal\n\n\t- literal\n#+EnD_sRc"

        assertEquals(listOf(
            OrgBlock.Paragraph("前の本文"),
            OrgBlock.Paragraph(literal),
            OrgBlock.ListItem(4, "*", "タブ付きの項目"),
            OrgBlock.Heading(3, "続き"),
        ), OrgParser.parse("前の本文\n$literal\n\t* タブ付きの項目\n*** 続き"))
    }

    @Test fun `unterminated literal blocks preserve all remaining lines`() {
        val literal = "#+BEGIN_EXAMPLE\n* literal\n\n- literal\n"

        assertEquals(listOf(OrgBlock.Paragraph(literal)), OrgParser.parse(literal))
    }
}
