package dev.orgmobile.reader

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import java.io.IOException
import java.io.InputStream
import java.io.InputStreamReader
import java.nio.charset.CodingErrorAction

data class OrgDocument(val name: String, val blocks: List<OrgBlock>)

fun interface DocumentSource {
    fun read(uri: Uri): OrgDocument
}

object DocumentDecoder {
    fun read(stream: InputStream): List<OrgBlock> {
        val decoder = Charsets.UTF_8.newDecoder()
            .onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT)
        return OrgParser.parse(InputStreamReader(stream, decoder).readText())
    }
}

class ContentDocumentSource(private val resolver: ContentResolver) : DocumentSource {
    override fun read(uri: Uri): OrgDocument {
        val blocks = resolver.openInputStream(uri)?.use(DocumentDecoder::read)
            ?: throw IOException("No document stream")
        val name = try {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                val column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (column >= 0 && cursor.moveToFirst()) cursor.getString(column) else null
            }
        } catch (_: RuntimeException) {
            // A provider may expose readable content without display-name metadata.
            null
        }
        return OrgDocument(name.orEmpty(), blocks)
    }
}
