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
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            setTextColor(0xFF202820.toInt())
            setTextIsSelectable(true)
            setLineSpacing(0f, 1.2f)
        }
        return BlockHolder(text)
    }

    override fun onBindViewHolder(holder: BlockHolder, position: Int) {
        val block = blocks[position]
        val text = holder.text
        fun dp(value: Int) = (value * text.resources.displayMetrics.density).roundToInt()
        text.setTypeface(null, Typeface.NORMAL)
        text.textSize = 17f
        ViewCompat.setAccessibilityHeading(text, block is OrgBlock.Heading)
        when (block) {
            is OrgBlock.Heading -> {
                text.text = block.text
                text.textSize = when (block.level) { 1 -> 25f; 2 -> 22f; else -> 19f }
                text.setTypeface(null, Typeface.BOLD)
                text.setPaddingRelative(0, dp(18), 0, dp(8))
            }
            is OrgBlock.Paragraph -> {
                text.text = block.text
                text.setPaddingRelative(0, dp(4), 0, dp(10))
            }
            is OrgBlock.ListItem -> {
                val marker = if (block.marker in listOf("-", "+", "*")) "•" else block.marker
                text.text = text.context.getString(R.string.list_item, marker, block.text)
                text.setPaddingRelative(dp(12 + block.indent.coerceAtMost(16) * 8), dp(4), 0, dp(4))
            }
        }
    }

    class BlockHolder(val text: TextView) : RecyclerView.ViewHolder(text)
}
