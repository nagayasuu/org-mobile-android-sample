package dev.orgmobile.reader

sealed interface OrgBlock {
    data class Heading(val level: Int, val text: String) : OrgBlock
    data class Paragraph(val text: String) : OrgBlock
    data class ListItem(val indent: Int, val marker: String, val text: String) : OrgBlock
}

object OrgParser {
    private val heading = Regex("^(\\*+) +(.+)$")
    private val listItem = Regex("^([ \\t]*)([-+]|\\d+[.)]|\\*)(?:[ \\t]+)(.*)$")
    private val beginBlock = Regex("^\\s*#\\+begin_(\\S+).*$", RegexOption.IGNORE_CASE)

    fun parse(text: String): List<OrgBlock> {
        val blocks = mutableListOf<OrgBlock>()
        val paragraph = mutableListOf<String>()
        var literalBlock: String? = null

        fun flushParagraph() {
            if (paragraph.isNotEmpty()) {
                blocks += OrgBlock.Paragraph(paragraph.joinToString("\n"))
                paragraph.clear()
            }
        }

        for (line in text.removePrefix("\uFEFF").lineSequence()) {
            if (literalBlock != null) {
                paragraph += line
                if (line.trim().equals("#+end_$literalBlock", ignoreCase = true)) {
                    literalBlock = null
                    flushParagraph()
                }
                continue
            }
            val begin = beginBlock.matchEntire(line)
            if (begin != null) {
                flushParagraph()
                literalBlock = begin.groupValues[1]
                paragraph += line
                continue
            }
            val title = heading.matchEntire(line)
            val item = listItem.matchEntire(line)
            when {
                line.isBlank() -> flushParagraph()
                title != null -> {
                    flushParagraph()
                    blocks += OrgBlock.Heading(title.groupValues[1].length, title.groupValues[2])
                }
                item != null && (item.groupValues[2] != "*" || item.groupValues[1].isNotEmpty()) -> {
                    flushParagraph()
                    val indent = item.groupValues[1].sumOf { if (it == '\t') 4 else 1 }
                    blocks += OrgBlock.ListItem(indent, item.groupValues[2], item.groupValues[3])
                }
                else -> paragraph += line
            }
        }
        flushParagraph()
        return blocks
    }
}
