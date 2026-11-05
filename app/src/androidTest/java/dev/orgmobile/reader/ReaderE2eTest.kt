package dev.orgmobile.reader

import android.app.UiModeManager
import android.content.ContentValues
import android.content.res.Configuration
import android.net.Uri
import android.os.Debug
import android.os.Environment
import android.os.SystemClock
import android.provider.MediaStore
import android.provider.Settings
import android.util.Log
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.accessibility.AccessibilityChecks
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.contrib.RecyclerViewActions
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiScrollable
import androidx.test.uiautomator.UiSelector
import androidx.test.uiautomator.Until
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TestName
import org.junit.runner.RunWith
import java.io.File

/** Run only on a disposable API 37 emulator, without accounts or personal files. */
@RunWith(AndroidJUnit4::class)
class ReaderE2eTest {
    @get:Rule val testName = TestName()
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val resolver = context.contentResolver
    private val device = UiDevice.getInstance(instrumentation)
    private var pickerPackage = ""
    private val documents = mutableListOf<Uri>()
    private var scenario: ActivityScenario<MainActivity>? = null
    private val prefix = "org-reader-e2e-"
    private val smoke = "${prefix}smoke.org"
    private val long = "${prefix}long.org"
    private val invalid = "${prefix}invalid.org"
    private val empty = "${prefix}empty.org"
    private val large = "${prefix}large.org"
    private val names = listOf(smoke, long, invalid, empty, large)
    private val documentUris = mutableMapOf<String, Uri>()
    private var restoreSettings: (() -> Unit)? = null

    @Before fun setUp() {
        assertEquals("Use the dedicated API 37 emulator", 37, android.os.Build.VERSION.SDK_INT)
        device.wakeUp()
        device.setOrientationNatural()
        releaseGrants()
        // Remove only fixtures owned by this app, including leftovers from interrupted runs.
        resolver.delete(
            MediaStore.Downloads.EXTERNAL_CONTENT_URI,
            "${MediaStore.MediaColumns.DISPLAY_NAME} IN (${names.joinToString { "?" }}) AND " +
                "${MediaStore.MediaColumns.OWNER_PACKAGE_NAME} = ?",
            (names + context.packageName).toTypedArray(),
        )
        stage(smoke, instrumentation.context.assets.open("smoke.org").use { it.readBytes() })
        stage(long, buildString {
            append("* 長文の確認\n")
            repeat(160) { append("- 確認行 ${it + 1}\n") }
            append("* 長文の末尾\n末尾まで読めました。\n")
        }.toByteArray(Charsets.UTF_8))
        stage(invalid, byteArrayOf(0xc3.toByte(), 0x28))
        stage(empty, byteArrayOf())
        scenario = ActivityScenario.launch(MainActivity::class.java)
        onView(withId(R.id.status)).check(matches(withText(R.string.initial_message)))
    }

    @After fun tearDown() {
        // Capture before closing the activity so failed picker/display stages remain visible.
        try {
            val output = outputDirectory()
            if (!device.takeScreenshot(File(output, "${testName.methodName}.png"))) {
                Log.w("ReaderE2E", "Could not capture test screenshot")
            }
            device.dumpWindowHierarchy(File(output, "${testName.methodName}.xml"))
        } catch (_: Exception) {
            Log.w("ReaderE2E", "Could not capture test diagnostics")
        } finally {
            try {
                scenario?.close()
                releaseGrants()
                documents.forEach { resolver.delete(it, null, null) }
            } finally {
                try {
                    restoreSettings?.invoke()
                } finally {
                    device.unfreezeRotation()
                }
            }
        }
    }

    @Test fun opensPublicSampleAndScrollsToEndOfLongDocument() {
        select(smoke)
        awaitDocument(smoke)
        assertRow("買い物メモ")
        assertRow("日本語の本文を読むためのサンプルです。\n次の行も同じ本文として表示されます。")
        assertRow("•  牛乳")
        assertRow("明日の予定")
        assertRow("1.  散歩する")
        select(long)
        awaitDocument(long)
        assertRow("長文の末尾")
        assertRow("末尾まで読めました。")
    }

    @Test fun cancellationAndRotationKeepDocumentAndReadingPosition() {
        select(long)
        awaitDocument(long)
        onView(withId(R.id.document)).perform(
            RecyclerViewActions.scrollToPosition<RecyclerView.ViewHolder>(80),
        )
        val before = position()
        assertTrue("Must scroll away from the start", before.first > 0)
        openPicker()
        device.pressBack()
        awaitDocument(long)
        assertEquals("Cancel must retain row and offset", before, position())
        device.setOrientationLeft()
        await("landscape and restored reading position") {
            var restored = false
            scenario!!.onActivity {
                restored = it.resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE &&
                    readingPosition(it.findViewById(R.id.document)) == before
            }
            restored
        }
        onView(withId(R.id.document_title)).check(matches(withText(long)))
        assertEquals("Rotation must retain row and offset", before, position())
        assertRow("末尾まで読めました。")
    }

    @Test fun invalidUtf8ShowsErrorAndValidSelectionRecovers() {
        select(invalid)
        assertTrue("Timed out waiting for UTF-8 error", device.wait(
            Until.hasObject(By.res(context.packageName, "status").text(context.getString(R.string.error_message))),
            TIMEOUT,
        ))
        onView(withId(R.id.status)).check(matches(withText(R.string.error_message)))
        select(smoke)
        awaitDocument(smoke)
        assertRow("買い物メモ")
        onView(withId(R.id.status)).check(matches(
            androidx.test.espresso.matcher.ViewMatchers.withEffectiveVisibility(
                androidx.test.espresso.matcher.ViewMatchers.Visibility.GONE,
            ),
        ))
    }

    @Test fun emptyDocumentClearsPreviousContentAndAllowsReselection() {
        select(smoke)
        awaitDocument(smoke)
        select(empty)
        awaitDocument(empty)
        onView(withId(R.id.status)).check(matches(withText(R.string.empty_message)))
        onView(withId(R.id.document)).check { view, error ->
            if (error != null) throw error
            assertEquals("Empty input must remove old rows", 0, (view as RecyclerView).adapter!!.itemCount)
        }
        select(smoke)
        awaitDocument(smoke)
        assertRow("買い物メモ")
    }

    @Test fun reopeningTheSameUpdatedDocumentReplacesContentAndStartsAtTop() {
        select(long)
        awaitDocument(long)
        onView(withId(R.id.document)).perform(
            RecyclerViewActions.scrollToPosition<RecyclerView.ViewHolder>(80),
        )
        assertTrue("Reload must begin from a scrolled document", position().first > 0)
        val originalUri = documentUris.getValue(long)
        checkNotNull(resolver.openOutputStream(originalUri, "wt")).use {
            it.write(buildString {
                append("* 更新後の見出し\n更新した本文です。\n")
                repeat(160) { append("- 更新項目 ${it + 1}\n") }
            }.toByteArray(Charsets.UTF_8))
        }
        select(long)
        assertTrue("Updated content did not replace the previous document", device.wait(
            Until.hasObject(By.text("更新後の見出し")), TIMEOUT,
        ))
        onView(withId(R.id.document_title)).check(matches(withText(long)))
        onView(withId(R.id.document)).check { view, error ->
            if (error != null) throw error
            assertEquals("Old rows must be replaced", 162, (view as RecyclerView).adapter!!.itemCount)
        }
        assertEquals("Reload must start at the first row", 0, position().first)
        assertRow("更新した本文です。")
        assertRow("•  更新項目 160")
    }

    @Test fun tenThousandItemsReachTheEndAndRecordLoadObservations() {
        val bytes = buildString {
            append("* 1万行の文書\n")
            repeat(10_000) { append("- 項目 ${it + 1}\n") }
            append("** 1万行の末尾\n1万行を読み終えました。\n")
        }.toByteArray(Charsets.UTF_8)
        stage(large, bytes)
        val selectedAt = select(large)
        awaitDocument(large)
        onView(withText("1万行の文書")).check(matches(isDisplayed()))
        val clickToFirstContentMs = SystemClock.elapsedRealtime() - selectedAt
        onView(withId(R.id.document)).check { view, error ->
            if (error != null) throw error
            assertEquals("Every input item must remain present", 10_003, (view as RecyclerView).adapter!!.itemCount)
        }
        onView(withId(R.id.document)).perform(
            RecyclerViewActions.scrollToPosition<RecyclerView.ViewHolder>(10_002),
        )
        onView(withText("•  項目 10000")).check(matches(isDisplayed()))
        onView(withText("1万行の末尾")).check(matches(isDisplayed()))
        onView(withText("1万行を読み終えました。")).check(matches(isDisplayed()))
        val memory = Debug.MemoryInfo().also { Debug.getMemoryInfo(it) }
        val runtime = Runtime.getRuntime()
        File(outputDirectory(), "large-document-observations.json").writeText(JSONObject().apply {
            put("item_count", 10_000)
            put("input_bytes", bytes.size)
            put("selection_click_to_first_content_ms", clickToFirstContentMs)
            put("instrumented_process_pss_after_scroll_kb", memory.totalPss)
            put("instrumented_process_java_heap_after_scroll_bytes", runtime.totalMemory() - runtime.freeMemory())
            put("performance_thresholds", JSONObject.NULL)
            put("scope", "Debug app plus instrumentation; PSS is a snapshot, not peak usage")
        }.toString(2))
    }

    @Test fun enlargedTextAndDisplayRemainUsableInBothNightModesAndLandscape() {
        val originalFontScale = Settings.System.getFloat(resolver, Settings.System.FONT_SCALE, 1f)
        val densityState = device.executeShellCommand("wm density")
        val originalDensity = context.resources.displayMetrics.densityDpi
        val overrideDensity = Regex("Override density: (\\d+)").find(densityState)?.groupValues?.get(1)
        val uiModeManager = context.getSystemService(UiModeManager::class.java)
        val originalNightValue = uiModeManager.nightMode
        val originalNightMode = when (originalNightValue) {
            UiModeManager.MODE_NIGHT_AUTO -> "auto"
            UiModeManager.MODE_NIGHT_YES -> "yes"
            UiModeManager.MODE_NIGHT_CUSTOM -> "custom"
            else -> "no"
        }
        scenario!!.close()
        scenario = null
        restoreSettings = {
            try {
                device.executeShellCommand("settings put system font_scale $originalFontScale")
            } finally {
                try {
                    device.executeShellCommand("wm density ${overrideDensity ?: "reset"}")
                } finally {
                    device.executeShellCommand("cmd uimode night $originalNightMode")
                    await("restore emulator settings") {
                        Settings.System.getFloat(resolver, Settings.System.FONT_SCALE, 1f) == originalFontScale &&
                            Regex("Override density: (\\d+)").find(device.executeShellCommand("wm density"))
                                ?.groupValues?.get(1) == overrideDensity && uiModeManager.nightMode == originalNightValue
                    }
                }
            }
        }
        val enlargedDensity = (originalDensity * 4 / 3).coerceAtMost(600)
        device.executeShellCommand("settings put system font_scale 2.0")
        device.executeShellCommand("wm density $enlargedDensity")
        device.executeShellCommand("cmd uimode night yes")
        scenario = ActivityScenario.launch(MainActivity::class.java)
        awaitConfiguration("enlarged night configuration") {
            it.fontScale >= 1.99f && it.densityDpi == enlargedDensity &&
                (it.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        }
        select(smoke)
        awaitDocument(smoke)
        assertRow("買い物メモ")
        assertRow("最後まで読めたことを確認するための本文です。")
        device.setOrientationLeft()
        awaitConfiguration("enlarged landscape configuration") {
            it.orientation == Configuration.ORIENTATION_LANDSCAPE && it.fontScale >= 1.99f
        }
        assertRow("最後まで読めたことを確認するための本文です。")
        device.executeShellCommand("cmd uimode night no")
        awaitConfiguration("day configuration") {
            (it.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_NO
        }
        onView(withId(R.id.open_file)).check(matches(isDisplayed()))
        assertRow("買い物メモ")
        assertRow("最後まで読めたことを確認するための本文です。")
    }

    @Test fun accessibilityChecksAndHeadingMetadataDescribeThePublicSample() {
        select(smoke)
        awaitDocument(smoke)
        AccessibilityChecks.enable().setRunChecksFromRootView(true)
        try {
            onView(withId(R.id.root)).check(AccessibilityChecks.accessibilityAssertion())
            onView(withText("買い物メモ")).check { view, error ->
                if (error != null) throw error
                assertTrue("Heading must be exposed to accessibility services", view.createAccessibilityNodeInfo().isHeading)
            }
            onView(withText("日本語の本文を読むためのサンプルです。\n次の行も同じ本文として表示されます。")).check { view, error ->
                if (error != null) throw error
                assertTrue("Paragraph must not be exposed as a heading", !view.createAccessibilityNodeInfo().isHeading)
            }
        } finally {
            AccessibilityChecks.disable()
        }
    }

    private fun awaitConfiguration(stage: String, predicate: (Configuration) -> Boolean) {
        await(stage) {
            var matches = false
            scenario!!.onActivity { matches = predicate(it.resources.configuration) }
            matches
        }
    }

    private fun outputDirectory(): File {
        val output = InstrumentationRegistry.getArguments().getString("additionalTestOutputDir")
            ?.let(::File) ?: File(context.getExternalFilesDir(null), "e2e")
        check(output.mkdirs() || output.isDirectory) { "Cannot create test output directory" }
        return output
    }

    private fun stage(name: String, bytes: ByteArray) {
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            // Unknown MIME preserves .org; text/plain makes MediaStore append .txt.
            put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream")
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val uri = checkNotNull(resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values))
        documents += uri
        documentUris[name] = uri
        checkNotNull(resolver.openOutputStream(uri)).use { it.write(bytes) }
        values.clear()
        values.put(MediaStore.MediaColumns.IS_PENDING, 0)
        assertEquals(1, resolver.update(uri, values, null, null))
        checkNotNull(resolver.query(uri, arrayOf(MediaStore.MediaColumns.DISPLAY_NAME), null, null, null)).use {
            assertTrue("Staged document missing", it.moveToFirst())
            assertEquals("MediaStore must preserve the .org filename", name, it.getString(0))
        }
    }

    private fun releaseGrants() {
        resolver.persistedUriPermissions.forEach {
            resolver.releasePersistableUriPermission(it.uri, android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    private fun openPicker() {
        Log.i("ReaderE2E", "${testName.methodName}: open system picker")
        onView(withId(R.id.open_file)).perform(click())
        // DocumentsUI replaces its window nodes while opening. Keep the package
        // string, rather than querying a UiObject2 captured during that transition.
        await("system DocumentsUI package") {
            pickerPackage = listOf("com.google.android.documentsui", "com.android.documentsui")
                .firstOrNull { device.hasObject(By.pkg(it)) }.orEmpty()
            pickerPackage.isNotEmpty()
        }
    }

    private fun select(name: String): Long {
        openPicker()
        // AOSP DocumentsUI resource selectors avoid depending on the system language.
        val roots = device.wait(Until.findObject(By.res(pickerPackage, "drawer_roots")), 1_000)
        if (roots == null) {
            val toolbar = device.wait(Until.findObject(By.res(pickerPackage, "toolbar")), TIMEOUT)
            assertNotNull("Picker toolbar missing", toolbar)
            val navigation = toolbar.findObject(By.clazz("android.widget.ImageButton"))
            assertNotNull("Picker navigation button missing", navigation)
            navigation.click()
        }
        val rootsList = device.wait(Until.findObject(By.res(pickerPackage, "roots_list")), TIMEOUT)
        assertNotNull("Picker roots list missing", rootsList)
        val downloads = rootsList.findObject(By.res("android", "title").text("Downloads"))
        assertNotNull("Downloads root missing; use an en-US emulator", downloads)
        downloads.click()
        assertTrue("Downloads navigation drawer did not close", device.wait(
            Until.gone(By.res(pickerPackage, "roots_list")), TIMEOUT,
        ))
        val list = UiScrollable(UiSelector().resourceId("$pickerPackage:id/dir_list"))
        list.setMaxSearchSwipes(10)
        assertTrue("Fixture not found in Downloads: $name", list.scrollIntoView(UiSelector().text(name)))
        val file = device.wait(Until.findObject(By.res("android", "title").text(name)), TIMEOUT)
        assertNotNull("Fixture selection missing: $name", file)
        val selectedAt = SystemClock.elapsedRealtime()
        assertTrue("Selecting the document did not leave the picker: $name",
            file.clickAndWait(Until.newWindow(), TIMEOUT),
        )
        return selectedAt
    }

    private fun awaitDocument(name: String) {
        Log.i("ReaderE2E", "${testName.methodName}: wait for document")
        assertTrue("Document did not load: $name", device.wait(
            Until.hasObject(By.res(context.packageName, "document_title").text(name)), TIMEOUT,
        ))
        onView(withId(R.id.document_title)).check(matches(withText(name)))
    }

    private fun assertRow(text: String) {
        onView(withId(R.id.document)).perform(
            RecyclerViewActions.scrollTo<RecyclerView.ViewHolder>(withText(text)),
        )
        onView(withText(text)).check(matches(isDisplayed()))
    }

    private fun readingPosition(view: RecyclerView): Pair<Int, Int> {
        val layout = view.layoutManager as LinearLayoutManager
        val row = layout.findFirstVisibleItemPosition()
        return row to (layout.findViewByPosition(row)?.top ?: Int.MIN_VALUE)
    }

    private fun position(): Pair<Int, Int> {
        var result = -1 to -1
        onView(withId(R.id.document)).check { view, error ->
            if (error != null) throw error
            result = readingPosition(view as RecyclerView)
        }
        return result
    }

    private fun await(stage: String, condition: () -> Boolean) {
        val deadline = SystemClock.uptimeMillis() + TIMEOUT
        while (SystemClock.uptimeMillis() < deadline) {
            instrumentation.waitForIdleSync()
            if (condition()) return
            SystemClock.sleep(50)
        }
        throw AssertionError("Timed out: $stage")
    }

    private companion object {
        const val TIMEOUT = 15_000L
    }
}
