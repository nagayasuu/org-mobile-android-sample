package dev.orgmobile.reader

import android.graphics.Typeface
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.view.ViewCompat
import androidx.recyclerview.widget.RecyclerView
import kotlin.math.roundToInt

class OrgAdapter : RecyclerView.Adapter<OrgAdapter.BlockHolder>() {
    private var blocks: List<OrgBlock> = emptyList()

    init {
        stateRestorationPolicy = StateRestorationPolicy.PREVENT_WHEN_EMPTY
    }

    fun show(blocks: List<OrgBlock>) {
        if (this.blocks === blocks) return
        val oldSize = this.blocks.size
        this.blocks = blocks
        if (oldSize > 0) notifyItemRangeRemoved(0, oldSize)
        if (blocks.isNotEmpty()) notifyItemRangeInserted(0, blocks.size)
    }

    override fun getItemCount() = blocks.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): BlockHolder {
        val text = TextView(parent.context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            )
            setTextColor(0xFF202820.toInt())
            setTextIsSelectable(true)
            setLineSpacing(0f, 1.2f)
        }
        return BlockHolder(text)
    }

    override fun onBindViewHolder(holder: BlockHolder, position: Int) {
        val block = blocks[position]
        val text = holder.text
        text.setTypeface(null, Typeface.NORMAL)
        text.textSize = 17f
        ViewCompat.setAccessibilityHeading(text, block is OrgBlock.Heading)
        when (block) {
            is OrgBlock.Heading -> bindHeading(text, block)
            is OrgBlock.Paragraph -> {
                text.text = block.text
                text.setPaddingRelative(0, text.dp(4), 0, text.dp(10))
            }
            is OrgBlock.ListItem -> bindListItem(text, block)
        }
    }

    private fun bindHeading(text: TextView, heading: OrgBlock.Heading) {
        text.text = heading.text
        text.textSize = when (heading.level) {
            1 -> 25f
            2 -> 22f
            else -> 19f
        }
        text.setTypeface(null, Typeface.BOLD)
        text.setPaddingRelative(0, text.dp(18), 0, text.dp(8))
    }

    private fun bindListItem(text: TextView, item: OrgBlock.ListItem) {
        val marker = if (item.marker in listOf("-", "+", "*")) "•" else item.marker
        text.text = text.context.getString(R.string.list_item, marker, item.text)
        val indent = text.dp(12 + item.indent.coerceAtMost(16) * 8)
        text.setPaddingRelative(indent, text.dp(4), 0, text.dp(4))
    }

    private fun TextView.dp(value: Int): Int =
        (value * resources.displayMetrics.density).roundToInt()

    class BlockHolder(val text: TextView) : RecyclerView.ViewHolder(text)
}
