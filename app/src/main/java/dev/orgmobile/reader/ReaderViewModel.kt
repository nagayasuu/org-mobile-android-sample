package dev.orgmobile.reader

import android.net.Uri
import androidx.core.net.toUri
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException

data class ReaderState(
    val document: OrgDocument? = null,
    val loading: Boolean = false,
    val failed: Boolean = false,
)

class ReaderViewModel(
    private val savedState: SavedStateHandle,
    private val source: DocumentSource,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    private val mutableState = MutableStateFlow(ReaderState())
    val state = mutableState.asStateFlow()
    private var readJob: Job? = null

    init {
        savedState.get<String>(DOCUMENT_URI)?.let { open(it.toUri()) }
    }

    fun open(uri: Uri) {
        readJob?.cancel()
        readJob = viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, failed = false)
            try {
                val document = withContext(ioDispatcher) { source.read(uri) }
                savedState[DOCUMENT_URI] = uri.toString()
                mutableState.value = ReaderState(document = document)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: IOException) {
                showFailure()
            } catch (_: SecurityException) {
                showFailure()
            } catch (_: IllegalArgumentException) {
                showFailure()
            }
        }
    }

    private fun showFailure() {
        mutableState.value = mutableState.value.copy(loading = false, failed = true)
    }

    companion object {
        const val DOCUMENT_URI = "document_uri"
    }
}
