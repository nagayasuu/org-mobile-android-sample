package dev.orgmobile.reader

import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ReaderViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    @Test fun `loads selected content and remembers successfully opened URI`() = runTest(dispatcher) {
        val handle = SavedStateHandle()
        val document = OrgDocument("notes.org", listOf(OrgBlock.Heading(1, "予定")))
        val model = ReaderViewModel(handle, DocumentSource { document }, dispatcher)

        model.open(Uri.parse("content://test/notes"))
        advanceUntilIdle()

        assertEquals(document, model.state.value.document)
        assertFalse(model.state.value.loading)
        assertFalse(model.state.value.failed)
        assertEquals("content://test/notes", handle.get<String>(ReaderViewModel.DOCUMENT_URI))
    }

    @Test fun `failed selection preserves previous document and allows retry`() = runTest(dispatcher) {
        val document = OrgDocument("notes.org", listOf(OrgBlock.Paragraph("保持する本文")))
        val handle = SavedStateHandle()
        var fail = false
        val model = ReaderViewModel(handle, DocumentSource {
            if (fail) throw IOException("unreadable")
            document
        }, dispatcher)
        model.open(Uri.parse("content://test/good"))
        advanceUntilIdle()

        fail = true
        model.open(Uri.parse("content://test/bad"))
        advanceUntilIdle()

        assertEquals(document, model.state.value.document)
        assertTrue(model.state.value.failed)
        assertFalse(model.state.value.loading)
        assertEquals("content://test/good", handle.get<String>(ReaderViewModel.DOCUMENT_URI))

        fail = false
        model.open(Uri.parse("content://test/retry"))
        advanceUntilIdle()
        assertFalse(model.state.value.failed)
    }

    @Test fun `reopens remembered document after process recreation`() = runTest(dispatcher) {
        val handle = SavedStateHandle(mapOf(ReaderViewModel.DOCUMENT_URI to "content://test/saved"))
        val document = OrgDocument("saved.org", listOf(OrgBlock.Paragraph("再表示")))
        var requested: Uri? = null

        val model = ReaderViewModel(handle, DocumentSource { uri -> requested = uri; document }, dispatcher)
        advanceUntilIdle()

        assertEquals("content://test/saved", requested.toString())
        assertEquals(document, model.state.value.document)
    }

    @Test fun `lost read permission produces a recoverable error`() = runTest(dispatcher) {
        val model = ReaderViewModel(SavedStateHandle(), DocumentSource {
            throw SecurityException("expired permission")
        }, dispatcher)

        model.open(Uri.parse("content://test/denied"))
        advanceUntilIdle()

        assertTrue(model.state.value.failed)
        assertFalse(model.state.value.loading)
    }
}
