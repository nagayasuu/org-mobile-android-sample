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
import org.junit.Assert.assertArrayEquals
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
    @Test fun `bundled sample matches the public fixture`() {
        val publicSample = checkNotNull(javaClass.classLoader!!.getResourceAsStream("smoke.org"))
            .use { it.readBytes() }
        val bundled = RuntimeEnvironment.getApplication().assets.open("smoke.org").use { it.readBytes() }
        assertArrayEquals(publicSample, bundled)
    }

    @Test fun `public sample renders Japanese paragraphs headings and list markers`() {
        val expected = listOf("買い物メモ", "日本語の本文を読むためのサンプルです。\n次の行も同じ本文として表示されます。",
            "•  牛乳", "•  パン", "•  全粒粉", "•  ライ麦", "明日の予定", "1.  散歩する",
            "2)  本を読む", "持ち物", "最後まで読めたことを確認するための本文です。")
        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            awaitStartup(activity)
            val view = activity.findViewById<RecyclerView>(R.id.document)
            assertEquals(expected.size, view.adapter!!.itemCount)
            for ((position, text) in expected.withIndex()) {
                view.scrollToPosition(position)
                layoutDocument(view)
                assertEquals(text, (view.findViewHolderForAdapterPosition(position) as OrgAdapter.BlockHolder).text.text.toString())
            }
        }
    }

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
            awaitStartup(activity)
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

    @Test fun `open button launches system document picker and cancellation keeps bundled sample`() {
        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            awaitStartup(activity)
            activity.findViewById<Button>(R.id.open_file).performClick()

            val request = shadowOf(activity).nextStartedActivityForResult
            assertEquals(Intent.ACTION_OPEN_DOCUMENT, request.intent.action)
            assertTrue(request.intent.hasCategory(Intent.CATEGORY_OPENABLE))
            assertEquals("*/*", request.intent.type)
            activity.activityResultRegistry.dispatchResult(request.requestCode, Activity.RESULT_CANCELED, null)
            shadowOf(Looper.getMainLooper()).idle()

            assertEquals("smoke.org", activity.findViewById<TextView>(R.id.document_title).text.toString())
            assertEquals(android.view.View.GONE, activity.findViewById<TextView>(R.id.status).visibility)
            assertTrue(activity.findViewById<Button>(R.id.open_file).isEnabled)
        }
    }

    @Test fun `renders parsed Japanese blocks and scrolls to last row of long document`() {
        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            val view = activity.findViewById<RecyclerView>(R.id.document)
            val adapter = view.adapter as OrgAdapter
            awaitStartup(activity)
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
            val offset = view.layoutManager!!.findViewByPosition(before)!!.top - view.paddingTop
            assertTrue("Expected a scrolled document, first visible row was $before", before > 0)

            activity.findViewById<Button>(R.id.open_file).performClick()
            val request = shadowOf(activity).nextStartedActivityForResult
            activity.activityResultRegistry.dispatchResult(request.requestCode, Activity.RESULT_CANCELED, null)
            layoutDocument(view)
            assertEquals(before, (view.layoutManager as LinearLayoutManager).findFirstVisibleItemPosition())
            assertEquals(offset, view.layoutManager!!.findViewByPosition(before)!!.top - view.paddingTop)

            controller.recreate()
            shadowOf(Looper.getMainLooper()).idle()
            val restored = controller.get().findViewById<RecyclerView>(R.id.document)
            layoutDocument(restored)

            assertEquals(before, (restored.layoutManager as LinearLayoutManager).findFirstVisibleItemPosition())
            assertEquals(offset, restored.layoutManager!!.findViewByPosition(before)!!.top - restored.paddingTop)
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

            assertTrue((view.layoutManager as LinearLayoutManager).findFirstVisibleItemPosition() > 0)
            file.writeText("* 更新した見出し\n新しい本文\n" +
                (1..1_000).joinToString("\n") { "- 更新項目 $it" }, Charsets.UTF_8)
            openSelectedSample(activity, expectedRows = 1_002)
            layoutDocument(view)

            assertEquals(1_002, view.adapter!!.itemCount)
            assertEquals(0, (view.layoutManager as LinearLayoutManager).findFirstVisibleItemPosition())
            assertEquals("更新した見出し", (view.findViewHolderForAdapterPosition(0) as OrgAdapter.BlockHolder).text.text.toString())
            assertEquals("新しい本文", (view.findViewHolderForAdapterPosition(1) as OrgAdapter.BlockHolder).text.text.toString())
            view.scrollToPosition(1_001)
            layoutDocument(view)
            assertEquals("•  更新項目 1000",
                (view.findViewHolderForAdapterPosition(1_001) as OrgAdapter.BlockHolder).text.text.toString())
        }
    }

    @Test fun `invalid UTF-8 preserves displayed content and a new selection recovers`() {
        val app = RuntimeEnvironment.getApplication()
        val file = File(app.cacheDir, "selected.org")
        file.writeText("* 保持する見出し\n元の本文", Charsets.UTF_8)
        val provider = SampleProvider()
        provider.attachInfo(app, ProviderInfo().apply { authority = "sample" })
        ShadowContentResolver.registerProviderInternal("sample", provider)

        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            openSelectedSample(activity, expectedRows = 2)
            file.writeBytes(byteArrayOf(0xC3.toByte(), 0x28))
            activity.findViewById<Button>(R.id.open_file).performClick()
            val request = shadowOf(activity).nextStartedActivityForResult
            activity.activityResultRegistry.dispatchResult(request.requestCode, Activity.RESULT_OK,
                Intent().setData(Uri.parse("content://sample/selected.org")))
            val status = activity.findViewById<TextView>(R.id.status)
            val timeout = System.nanoTime() + 5_000_000_000L
            while (status.text.toString() != activity.getString(R.string.error_message) &&
                System.nanoTime() < timeout) {
                shadowOf(Looper.getMainLooper()).idle()
                Thread.sleep(10)
            }

            assertEquals(activity.getString(R.string.error_message), status.text.toString())
            assertTrue(activity.findViewById<Button>(R.id.open_file).isEnabled)
            val view = activity.findViewById<RecyclerView>(R.id.document)
            layoutDocument(view)
            assertEquals(2, view.adapter!!.itemCount)
            assertEquals("保持する見出し",
                (view.findViewHolderForAdapterPosition(0) as OrgAdapter.BlockHolder).text.text.toString())

            file.writeText("* 再選択\n新しい本文\n- 項目", Charsets.UTF_8)
            openSelectedSample(activity, expectedRows = 3)
            layoutDocument(view)
            assertEquals(android.view.View.GONE, status.visibility)
            assertEquals("再選択",
                (view.findViewHolderForAdapterPosition(0) as OrgAdapter.BlockHolder).text.text.toString())
        }
    }

    @Test fun `startup displays bundled sample and keeps it after rotation`() {
        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            awaitStartup(controller.get())
            controller.recreate()
            awaitStartup(controller.get())
        }
    }

    @Test fun `empty selection clears old rows and a new selection recovers`() {
        val app = RuntimeEnvironment.getApplication()
        val file = File(app.cacheDir, "selected.org")
        file.writeText("", Charsets.UTF_8)
        val provider = SampleProvider()
        provider.attachInfo(app, ProviderInfo().apply { authority = "sample" })
        ShadowContentResolver.registerProviderInternal("sample", provider)

        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            awaitStartup(activity)
            openSelectedSample(activity, expectedRows = 0)
            val status = activity.findViewById<TextView>(R.id.status)
            assertEquals(android.view.View.VISIBLE, status.visibility)
            assertEquals(activity.getString(R.string.empty_message), status.text.toString())
            assertEquals("selected.org", activity.findViewById<TextView>(R.id.document_title).text.toString())

            file.writeText("* 再選択\n正常な本文", Charsets.UTF_8)
            openSelectedSample(activity, expectedRows = 2)
            val view = activity.findViewById<RecyclerView>(R.id.document)
            layoutDocument(view)
            assertEquals(android.view.View.GONE, status.visibility)
            assertEquals("再選択", (view.findViewHolderForAdapterPosition(0) as OrgAdapter.BlockHolder).text.text.toString())
        }
    }

    @Test fun `ten thousand selected items preserve their count and final content`() {
        val app = RuntimeEnvironment.getApplication()
        File(app.cacheDir, "selected.org").writeText(buildString {
            append("* 1万行の文書\n")
            repeat(10_000) { append("- 項目 ${it + 1}\n") }
            append("** 1万行の末尾\n1万行を読み終えました。\n")
        }, Charsets.UTF_8)
        val provider = SampleProvider()
        provider.attachInfo(app, ProviderInfo().apply { authority = "sample" })
        ShadowContentResolver.registerProviderInternal("sample", provider)

        Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
            val activity = controller.get()
            awaitStartup(activity)
            openSelectedSample(activity, expectedRows = 10_003)
            val view = activity.findViewById<RecyclerView>(R.id.document)
            layoutDocument(view)
            assertEquals("1万行の文書", (view.findViewHolderForAdapterPosition(0) as OrgAdapter.BlockHolder).text.text.toString())
            view.scrollToPosition(10_002)
            layoutDocument(view)
            for ((position, expected) in listOf(10_000 to "•  項目 10000",
                    10_001 to "1万行の末尾", 10_002 to "1万行を読み終えました。")) {
                assertEquals(expected, (view.findViewHolderForAdapterPosition(position) as OrgAdapter.BlockHolder).text.text.toString())
            }
        }
    }

    @Test fun `enlarged text retains controls and document in portrait landscape and night modes`() {
        val originalFontScale = RuntimeEnvironment.getApplication().resources.configuration.fontScale
        try {
            RuntimeEnvironment.setFontScale(2f)
            for (qualifiers in listOf("w360dp-h640dp-port-night-xhdpi", "w360dp-h640dp-port-notnight-xhdpi",
                    "w640dp-h360dp-land-night-xhdpi", "w640dp-h360dp-land-notnight-xhdpi")) {
                RuntimeEnvironment.setQualifiers(qualifiers)
                Robolectric.buildActivity(MainActivity::class.java).setup().use { controller ->
                    val activity = controller.get()
                    awaitStartup(activity)
                    val root = activity.findViewById<android.view.View>(R.id.root)
                    val density = activity.resources.displayMetrics.density
                    val width = (activity.resources.configuration.screenWidthDp * density).toInt()
                    val height = (activity.resources.configuration.screenHeightDp * density).toInt()
                    root.forceLayout()
                    activity.findViewById<RecyclerView>(R.id.document).forceLayout()
                    root.measure(
                        android.view.View.MeasureSpec.makeMeasureSpec(width, android.view.View.MeasureSpec.EXACTLY),
                        android.view.View.MeasureSpec.makeMeasureSpec(height, android.view.View.MeasureSpec.EXACTLY),
                    )
                    root.layout(0, 0, width, height)
                    val button = activity.findViewById<Button>(R.id.open_file)
                    val view = activity.findViewById<RecyclerView>(R.id.document)
                    assertEquals(2f, activity.resources.configuration.fontScale)
                    assertTrue(button.isShown && button.isEnabled)
                    assertTrue(button.height >= 48 * density)
                    assertTrue(button.top >= 0 && button.bottom <= height && button.right <= width)
                    assertTrue("Viewport ${view.top}..${view.bottom}, height=$height, title=${activity.findViewById<TextView>(R.id.document_title).height}, button=${button.height}", view.height > 0 && view.bottom <= height)
                    view.scrollToPosition(view.adapter!!.itemCount - 1)
                    shadowOf(Looper.getMainLooper()).idle()
                    val last = view.findViewHolderForAdapterPosition(view.adapter!!.itemCount - 1) as OrgAdapter.BlockHolder
                    assertEquals("最後まで読めたことを確認するための本文です。", last.text.text.toString())
                    button.performClick()
                    assertEquals(Intent.ACTION_OPEN_DOCUMENT, shadowOf(activity).nextStartedActivityForResult.intent.action)
                }
            }
        } finally {
            RuntimeEnvironment.setFontScale(originalFontScale)
        }
    }

    private fun awaitStartup(activity: MainActivity) {
        val timeout = System.nanoTime() + 5_000_000_000L
        while ((activity.findViewById<TextView>(R.id.document_title).text.toString() != "smoke.org" ||
                !activity.findViewById<Button>(R.id.open_file).isEnabled) && System.nanoTime() < timeout) {
            shadowOf(Looper.getMainLooper()).idle()
            Thread.sleep(10)
        }
        assertEquals("smoke.org", activity.findViewById<TextView>(R.id.document_title).text.toString())
        val view = activity.findViewById<RecyclerView>(R.id.document)
        layoutDocument(view)
        assertEquals("買い物メモ", (view.findViewHolderForAdapterPosition(0) as OrgAdapter.BlockHolder).text.text.toString())
        assertTrue(activity.findViewById<Button>(R.id.open_file).isEnabled)
    }

    private fun awaitReady(activity: MainActivity) {
        val timeout = System.nanoTime() + 5_000_000_000L
        while (!activity.findViewById<Button>(R.id.open_file).isEnabled && System.nanoTime() < timeout) {
            shadowOf(Looper.getMainLooper()).idle()
            Thread.sleep(10)
        }
        shadowOf(Looper.getMainLooper()).idle()
    }

    private fun openSelectedSample(activity: MainActivity, expectedRows: Int = 1_000) {
        awaitReady(activity)
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
        shadowOf(Looper.getMainLooper()).idle()
        view.forceLayout()
        view.measure(
            android.view.View.MeasureSpec.makeMeasureSpec(1080, android.view.View.MeasureSpec.EXACTLY),
            android.view.View.MeasureSpec.makeMeasureSpec(1200, android.view.View.MeasureSpec.EXACTLY),
        )
        view.layout(0, 0, 1080, 1200)
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
