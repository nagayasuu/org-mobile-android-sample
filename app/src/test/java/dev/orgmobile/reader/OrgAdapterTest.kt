package dev.orgmobile.reader

import android.view.View
import android.widget.FrameLayout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import kotlin.math.ceil

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class OrgAdapterTest {
    @Test fun `selectable rows provide at least a 48dp touch target`() {
        val parent = FrameLayout(RuntimeEnvironment.getApplication())
        val adapter = OrgAdapter()
        adapter.show(listOf(OrgBlock.Heading(1, "見出し"), OrgBlock.Paragraph("本文"),
            OrgBlock.ListItem(0, "-", "項目")))
        val minimum = ceil(48 * parent.resources.displayMetrics.density.toDouble()).toInt()
        for (position in 0 until adapter.itemCount) {
            val holder = adapter.onCreateViewHolder(parent, 0)
            adapter.onBindViewHolder(holder, position)
            holder.text.measure(View.MeasureSpec.makeMeasureSpec(minimum * 5, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
            assertTrue("Row $position must be selectable", holder.text.isTextSelectable)
            // A tall font can hide a missing floor; shorter content must stay tappable too.
            assertTrue("Row $position must retain a 48dp minimum", holder.text.minHeight >= minimum)
            assertTrue("Row $position must have a 48dp touch target", holder.text.measuredHeight >= minimum)
        }
    }

    @Test fun `recycled rows expose headings only for heading blocks`() {
        val parent = FrameLayout(RuntimeEnvironment.getApplication())
        val adapter = OrgAdapter()
        adapter.show(listOf(OrgBlock.Heading(1, "見出し"), OrgBlock.Paragraph("本文"),
            OrgBlock.ListItem(0, "-", "項目")))
        val holder = adapter.onCreateViewHolder(parent, 0)
        for (position in listOf(0, 1, 0, 2)) {
            adapter.onBindViewHolder(holder, position)
            assertEquals("Heading metadata for row $position", position == 0,
                holder.text.isAccessibilityHeading)
        }
    }
}
