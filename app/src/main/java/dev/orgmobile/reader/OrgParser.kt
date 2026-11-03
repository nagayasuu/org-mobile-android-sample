package dev.orgmobile.reader

sealed interface OrgBlock {
    data class Heading(val level: Int, val text: String) : OrgBlock
    data class Paragraph(val text: String) : OrgBlock
    data class ListItem(val indent: Int, val marker: String, val text: String) : OrgBlock
}

object OrgParser {
    // Temporary CI regression verification; never merge this helper.
    fun coverageGateProbe(value: Int): Int = if (value > 0) 1 else 0

    private val heading = Regex("^(\\*+) +(.+)$")
    private val listItem = Regex("^([ \\t]*)([-+]|\\d+[.)]|\\*)(?:[ \\t]+)(.*)$")
    private val beginBlock = Regex("^\\s*#\\+begin_(\\S+).*$", RegexOption.IGNORE_CASE)

    fun parse(text: String): List<OrgBlock> = Parser().parse(text)

    private fun parseBlock(line: String): OrgBlock? {
        heading.matchEntire(line)?.let { title ->
            return OrgBlock.Heading(title.groupValues[1].length, title.groupValues[2])
        }
        val item = listItem.matchEntire(line) ?: return null
        val (whitespace, marker, text) = item.destructured
        if (marker == "*" && whitespace.isEmpty()) return null
        val indent = whitespace.sumOf { if (it == '\t') 4 else 1 }
        return OrgBlock.ListItem(indent, marker, text)
    }

    private class Parser {
        private val blocks = mutableListOf<OrgBlock>()
        private val paragraph = mutableListOf<String>()
        private var literalBlock: String? = null

        fun parse(text: String): List<OrgBlock> {
            text.removePrefix("\uFEFF").lineSequence().forEach(::appendLine)
            flushParagraph()
            return blocks
        }

        private fun appendLine(line: String) {
            if (literalBlock != null) {
                appendLiteralLine(line)
                return
            }
            val begin = beginBlock.matchEntire(line)
            if (begin != null) {
                flushParagraph()
                literalBlock = begin.groupValues[1]
                paragraph += line
                return
            }
            appendContentLine(line)
        }

        private fun appendContentLine(line: String) {
            val block = parseBlock(line)
            when {
                line.isBlank() -> flushParagraph()
                block != null -> {
                    flushParagraph()
                    blocks += block
                }
                else -> paragraph += line
            }
        }

        private fun appendLiteralLine(line: String) {
            paragraph += line
            if (line.trim().equals("#+end_$literalBlock", ignoreCase = true)) {
                literalBlock = null
                flushParagraph()
            }
        }

        private fun flushParagraph() {
            if (paragraph.isNotEmpty()) {
                blocks += OrgBlock.Paragraph(paragraph.joinToString("\n"))
                paragraph.clear()
            }
        }
    }
}
