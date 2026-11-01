package dev.orgmobile.reader

import android.content.ContentProvider
import android.content.ContentValues
import android.content.pm.ProviderInfo
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowContentResolver
import java.io.File
import java.nio.charset.CharacterCodingException

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ContentDocumentSourceTest {
    private val app = RuntimeEnvironment.getApplication()
    private val uri = Uri.parse("content://resource-test/sample.org")
    private lateinit var file: File
    private lateinit var provider: TrackingProvider
    private lateinit var source: ContentDocumentSource

    @Before fun setUp() {
        file = File(app.cacheDir, "resource-test.org")
        provider = TrackingProvider(file)
        provider.attachInfo(app, ProviderInfo().apply { authority = uri.authority })
        ShadowContentResolver.registerProviderInternal(uri.authority!!, provider)
        source = ContentDocumentSource(app.contentResolver)
    }

    @Test fun `successful read closes the stream and metadata cursor`() {
        file.writeText("* 日本語\n本文", Charsets.UTF_8)

        val document = source.read(uri)

        assertEquals(OrgDocument("sample.org", listOf(
            OrgBlock.Heading(1, "日本語"), OrgBlock.Paragraph("本文"),
        )), document)
        assertFalse(provider.descriptor.fileDescriptor.valid())
        assertTrue(provider.cursor!!.isClosed)
    }

    @Test fun `malformed UTF-8 closes the stream before reporting failure`() {
        file.writeBytes(byteArrayOf(0xC3.toByte(), 0x28))

        assertThrows(CharacterCodingException::class.java) { source.read(uri) }

        assertFalse(provider.descriptor.fileDescriptor.valid())
    }

    @Test fun `unavailable display name still returns readable content`() {
        file.writeText("本文", Charsets.UTF_8)
        provider.denyMetadata = true

        val document = source.read(uri)

        assertEquals(OrgDocument("", listOf(OrgBlock.Paragraph("本文"))), document)
        assertFalse(provider.descriptor.fileDescriptor.valid())
    }

    class TrackingProvider(private val file: File) : ContentProvider() {
        lateinit var descriptor: ParcelFileDescriptor
        var cursor: MatrixCursor? = null
        var denyMetadata = false

        override fun onCreate() = true
        override fun getType(uri: Uri) = "text/plain"

        override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
            check(mode == "r") { "The reader must request read-only access" }
            return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
                .also { descriptor = it }
        }

        override fun query(
            uri: Uri, projection: Array<out String>?, selection: String?,
            selectionArgs: Array<out String>?, sortOrder: String?,
        ): Cursor {
            if (denyMetadata) throw SecurityException("Metadata unavailable")
            return MatrixCursor(arrayOf(OpenableColumns.DISPLAY_NAME))
                .apply { addRow(arrayOf("sample.org")) }
                .also { cursor = it }
        }

        override fun insert(uri: Uri, values: ContentValues?): Uri? =
            throw UnsupportedOperationException()
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) =
            throw UnsupportedOperationException()
        override fun update(
            uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?,
        ) = throw UnsupportedOperationException()
    }
}
