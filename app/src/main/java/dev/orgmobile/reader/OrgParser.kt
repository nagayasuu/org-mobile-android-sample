package dev.orgmobile.reader

sealed interface OrgBlock {
    data class Heading(val level: Int, val text: String) : OrgBlock
    data class Paragraph(val text: String) : OrgBlock
    data class ListItem(val indent: Int, val marker: String, val text: String) : OrgBlock
}

object OrgParser {
    // Temporary CI gate verification; never merge this helper.
    fun coverageGateProbe(value: Int): Int {
        var score = 0
        if (value == 1) score += 1
        if (value == 2) score += 2
        if (value == 3) score += 3
        if (value == 4) score += 4
        if (value == 5) score += 5
        if (value == 6) score += 6
        if (value == 7) score += 7
        if (value == 8) score += 8
        if (value == 9) score += 9
        if (value == 10) score += 10
        if (value == 11) score += 11
        if (value == 12) score += 12
        if (value == 13) score += 13
        if (value == 14) score += 14
        if (value == 15) score += 15
        if (value == 16) score += 16
        if (value == 17) score += 17
        if (value == 18) score += 18
        if (value == 19) score += 19
        if (value == 20) score += 20
        if (value == 21) score += 21
        if (value == 22) score += 22
        if (value == 23) score += 23
        if (value == 24) score += 24
        if (value == 25) score += 25
        if (value == 26) score += 26
        if (value == 27) score += 27
        if (value == 28) score += 28
        if (value == 29) score += 29
        if (value == 30) score += 30
        if (value == 31) score += 31
        if (value == 32) score += 32
        if (value == 33) score += 33
        if (value == 34) score += 34
        if (value == 35) score += 35
        if (value == 36) score += 36
        if (value == 37) score += 37
        if (value == 38) score += 38
        if (value == 39) score += 39
        if (value == 40) score += 40
        if (value == 41) score += 41
        if (value == 42) score += 42
        if (value == 43) score += 43
        if (value == 44) score += 44
        if (value == 45) score += 45
        if (value == 46) score += 46
        if (value == 47) score += 47
        if (value == 48) score += 48
        if (value == 49) score += 49
        if (value == 50) score += 50
        if (value == 51) score += 51
        if (value == 52) score += 52
        if (value == 53) score += 53
        if (value == 54) score += 54
        if (value == 55) score += 55
        if (value == 56) score += 56
        if (value == 57) score += 57
        if (value == 58) score += 58
        if (value == 59) score += 59
        if (value == 60) score += 60
        return score
    }

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
