package dev.orgmobile.reader

import android.content.ContentValues
import android.content.res.Configuration
import android.net.Uri
import android.os.Environment
import android.os.SystemClock
import android.provider.MediaStore
import android.util.Log
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.click
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
import java.util.regex.Pattern

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

    @Before fun setUp() {
        assertEquals("Use the dedicated API 37 emulator", 37, android.os.Build.VERSION.SDK_INT)
        device.wakeUp()
        device.setOrientationNatural()
        releaseGrants()
        // Remove only fixtures owned by this app, including leftovers from interrupted runs.
        resolver.delete(
            MediaStore.Downloads.EXTERNAL_CONTENT_URI,
            "${MediaStore.MediaColumns.DISPLAY_NAME} IN (?, ?, ?) AND " +
                "${MediaStore.MediaColumns.OWNER_PACKAGE_NAME} = ?",
            arrayOf(smoke, long, invalid, context.packageName),
        )
        stage(smoke, instrumentation.context.assets.open("smoke.org").use { it.readBytes() })
        stage(long, buildString {
            append("* 長文の確認\n")
            repeat(160) { append("- 確認行 ${it + 1}\n") }
            append("* 長文の末尾\n末尾まで読めました。\n")
        }.toByteArray(Charsets.UTF_8))
        stage(invalid, byteArrayOf(0xc3.toByte(), 0x28))
        scenario = ActivityScenario.launch(MainActivity::class.java)
        onView(withId(R.id.status)).check(matches(withText(R.string.initial_message)))
    }

    @After fun tearDown() {
        // Capture before closing the activity so failed picker/display stages remain visible.
        try {
            val output = InstrumentationRegistry.getArguments().getString("additionalTestOutputDir")
                ?.let(::File) ?: File(context.getExternalFilesDir(null), "e2e")
            output.mkdirs()
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
                device.unfreezeRotation()
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
        val picker = device.wait(Until.findObject(
            By.pkg(Pattern.compile("com\\.(android|google\\.android)\\.documentsui")),
        ), TIMEOUT)
        assertNotNull("System DocumentsUI did not open", picker)
        pickerPackage = picker.applicationPackage
    }

    private fun select(name: String) {
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
        assertTrue("Selecting the document did not leave the picker: $name",
            file.clickAndWait(Until.newWindow(), TIMEOUT),
        )
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
