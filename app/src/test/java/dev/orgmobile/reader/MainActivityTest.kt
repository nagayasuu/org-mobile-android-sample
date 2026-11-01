package dev.orgmobile.reader

import android.app.Activity
import android.content.ContentProvider
import android.content.ContentValues
import android.content.Intent
import android.content.pm.ProviderInfo
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import android.widget.Button
import android.widget.TextView
import androidx.core.view.WindowInsetsControllerCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowContentResolver
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class MainActivityTest {
    @Test
    @Config(qualifiers = "night")
    fun `system bar icons stay readable on the light reader background in dark device mode`() {
        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            val bars = WindowInsetsControllerCompat(activity.window, activity.window.decorView)
            assertTrue(bars.isAppearanceLightStatusBars)
            assertTrue(bars.isAppearanceLightNavigationBars)
        }
    }

    @Test fun `selected content URI is read and displayed and survives rotation and cancellation`() {
        val app = RuntimeEnvironment.getApplication()
        File(app.cacheDir, "selected.org").writeText("* 予定\n日本語の本文\n- 牛乳", Charsets.UTF_8)
        val provider = SampleProvider()
        provider.attachInfo(app, ProviderInfo().apply { authority = "sample" })
        ShadowContentResolver.registerProviderInternal("sample", provider)

        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            var activity = controller.get()
            shadowOf(Looper.getMainLooper()).idle()
            activity.findViewById<Button>(R.id.open_file).performClick()
            val request = shadowOf(activity).nextStartedActivityForResult

            activity.activityResultRegistry.dispatchResult(request.requestCode, Activity.RESULT_OK,
                Intent().setData(Uri.parse("content://sample/selected.org")))
            val timeout = System.nanoTime() + 5_000_000_000L
            while (activity.findViewById<TextView>(R.id.document_title).text.toString() != "selected.org" &&
                System.nanoTime() < timeout) {
                shadowOf(Looper.getMainLooper()).idle()
                Thread.sleep(10)
            }
            assertEquals("selected.org", activity.findViewById<TextView>(R.id.document_title).text.toString())
            assertEquals(3, activity.findViewById<RecyclerView>(R.id.document).adapter!!.itemCount)

            controller.recreate()
            activity = controller.get()
            shadowOf(Looper.getMainLooper()).idle()
            assertEquals("selected.org", activity.findViewById<TextView>(R.id.document_title).text.toString())
            assertEquals(3, activity.findViewById<RecyclerView>(R.id.document).adapter!!.itemCount)

            activity.findViewById<Button>(R.id.open_file).performClick()
            val cancelled = shadowOf(activity).nextStartedActivityForResult
            activity.activityResultRegistry.dispatchResult(cancelled.requestCode, Activity.RESULT_CANCELED, null)
            shadowOf(Looper.getMainLooper()).idle()
            assertEquals(3, activity.findViewById<RecyclerView>(R.id.document).adapter!!.itemCount)
        }
    }

    @Test fun `open button launches system document picker and cancellation keeps initial screen`() {
        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            shadowOf(Looper.getMainLooper()).idle()
            activity.findViewById<Button>(R.id.open_file).performClick()

            val request = shadowOf(activity).nextStartedActivityForResult
            assertEquals(Intent.ACTION_OPEN_DOCUMENT, request.intent.action)
            assertTrue(request.intent.hasCategory(Intent.CATEGORY_OPENABLE))
            assertEquals("*/*", request.intent.type)
            activity.activityResultRegistry.dispatchResult(request.requestCode, Activity.RESULT_CANCELED, null)
            shadowOf(Looper.getMainLooper()).idle()

            assertEquals(activity.getString(R.string.initial_message),
                activity.findViewById<TextView>(R.id.status).text.toString())
            assertTrue(activity.findViewById<Button>(R.id.open_file).isEnabled)
        }
    }

    @Test fun `renders parsed Japanese blocks and scrolls to last row of long document`() {
        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            val view = activity.findViewById<RecyclerView>(R.id.document)
            val adapter = view.adapter as OrgAdapter
            val source = "* 日本語の見出し\n本文です\n" + (1..1_000).joinToString("\n") { "- 項目 $it" }

            adapter.show(OrgParser.parse(source))
            view.measure(
                android.view.View.MeasureSpec.makeMeasureSpec(1080, android.view.View.MeasureSpec.EXACTLY),
                android.view.View.MeasureSpec.makeMeasureSpec(1200, android.view.View.MeasureSpec.EXACTLY),
            )
            view.layout(0, 0, 1080, 1200)
            assertEquals("日本語の見出し", (view.findViewHolderForAdapterPosition(0) as OrgAdapter.BlockHolder).text.text.toString())
            assertEquals("本文です", (view.findViewHolderForAdapterPosition(1) as OrgAdapter.BlockHolder).text.text.toString())

            view.scrollToPosition(adapter.itemCount - 1)
            view.layout(0, 0, 1080, 1200)
            shadowOf(Looper.getMainLooper()).idle()

            val last = view.findViewHolderForAdapterPosition(adapter.itemCount - 1) as OrgAdapter.BlockHolder
            assertEquals("•  項目 1000", last.text.text.toString())
        }
    }

    @Test fun `rotation preserves reading position in a long selected document`() {
        val app = RuntimeEnvironment.getApplication()
        File(app.cacheDir, "selected.org").writeText(
            (1..1_000).joinToString("\n") { "- 項目 $it" }, Charsets.UTF_8)
        val provider = SampleProvider()
        provider.attachInfo(app, ProviderInfo().apply { authority = "sample" })
        ShadowContentResolver.registerProviderInternal("sample", provider)

        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            openSelectedSample(activity)
            val view = activity.findViewById<RecyclerView>(R.id.document)
            layoutDocument(view)
            view.scrollToPosition(500)
            layoutDocument(view)
            val before = (view.layoutManager as LinearLayoutManager).findFirstVisibleItemPosition()
            assertTrue("Expected a scrolled document, first visible row was $before", before > 0)

            controller.recreate()
            shadowOf(Looper.getMainLooper()).idle()
            val restored = controller.get().findViewById<RecyclerView>(R.id.document)
            layoutDocument(restored)

            assertEquals(before, (restored.layoutManager as LinearLayoutManager).findFirstVisibleItemPosition())
        }
    }

    @Test fun `reopening a changed file replaces old rows and starts at its beginning`() {
        val app = RuntimeEnvironment.getApplication()
        val file = File(app.cacheDir, "selected.org")
        file.writeText((1..1_000).joinToString("\n") { "- 古い項目 $it" }, Charsets.UTF_8)
        val provider = SampleProvider()
        provider.attachInfo(app, ProviderInfo().apply { authority = "sample" })
        ShadowContentResolver.registerProviderInternal("sample", provider)

        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            openSelectedSample(activity)
            val view = activity.findViewById<RecyclerView>(R.id.document)
            layoutDocument(view)
            view.scrollToPosition(500)
            layoutDocument(view)

            file.writeText("* 更新した見出し\n新しい本文", Charsets.UTF_8)
            openSelectedSample(activity, expectedRows = 2)
            layoutDocument(view)

            assertEquals(2, view.adapter!!.itemCount)
            assertEquals(0, (view.layoutManager as LinearLayoutManager).findFirstVisibleItemPosition())
            assertEquals("更新した見出し", (view.findViewHolderForAdapterPosition(0) as OrgAdapter.BlockHolder).text.text.toString())
            assertEquals("新しい本文", (view.findViewHolderForAdapterPosition(1) as OrgAdapter.BlockHolder).text.text.toString())
        }
    }

    private fun openSelectedSample(activity: MainActivity, expectedRows: Int = 1_000) {
        shadowOf(Looper.getMainLooper()).idle()
        activity.findViewById<Button>(R.id.open_file).performClick()
        val request = shadowOf(activity).nextStartedActivityForResult
        activity.activityResultRegistry.dispatchResult(request.requestCode, Activity.RESULT_OK,
            Intent().setData(Uri.parse("content://sample/selected.org")))
        val timeout = System.nanoTime() + 5_000_000_000L
        val view = activity.findViewById<RecyclerView>(R.id.document)
        while ((view.adapter!!.itemCount != expectedRows || !activity.findViewById<Button>(R.id.open_file).isEnabled) &&
            System.nanoTime() < timeout) {
            shadowOf(Looper.getMainLooper()).idle()
            Thread.sleep(10)
        }
        assertEquals(expectedRows, view.adapter!!.itemCount)
        assertTrue(activity.findViewById<Button>(R.id.open_file).isEnabled)
    }

    private fun layoutDocument(view: RecyclerView) {
        view.measure(
            android.view.View.MeasureSpec.makeMeasureSpec(1080, android.view.View.MeasureSpec.EXACTLY),
            android.view.View.MeasureSpec.makeMeasureSpec(1200, android.view.View.MeasureSpec.EXACTLY),
        )
        view.layout(0, 0, 1080, 1200)
        shadowOf(Looper.getMainLooper()).idle()
    }

    class SampleProvider : ContentProvider() {
        override fun onCreate() = true
        override fun getType(uri: Uri) = "text/plain"
        override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor =
            ParcelFileDescriptor.open(File(context!!.cacheDir, "selected.org"), ParcelFileDescriptor.MODE_READ_ONLY)
        override fun query(uri: Uri, projection: Array<out String>?, selection: String?,
            selectionArgs: Array<out String>?, sortOrder: String?): Cursor =
            MatrixCursor(arrayOf(OpenableColumns.DISPLAY_NAME)).apply { addRow(arrayOf("selected.org")) }
        override fun insert(uri: Uri, values: ContentValues?): Uri? = throw UnsupportedOperationException()
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = throw UnsupportedOperationException()
        override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) =
            throw UnsupportedOperationException()
    }
}
