package dev.orgmobile.reader

import android.content.Intent
import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val model: ReaderViewModel by viewModels {
        viewModelFactory {
            initializer {
                ReaderViewModel(createSavedStateHandle(), ContentDocumentSource(contentResolver))
            }
        }
    }

    private val openDocument = registerForActivityResult(object : ActivityResultContracts.OpenDocument() {
        override fun createIntent(context: Context, input: Array<String>): Intent =
            super.createIntent(context, input).addCategory(Intent.CATEGORY_OPENABLE)
    }) { uri ->
        if (uri != null) {
            try {
                contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            } catch (_: SecurityException) {
                // Some providers grant access only for this session; reading can still work.
            }
            model.open(uri)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
        )
        setContentView(R.layout.activity_main)
        val root = findViewById<View>(R.id.root)
        val horizontalPadding = root.paddingLeft
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            view.setPadding(horizontalPadding + bars.left, bars.top, horizontalPadding + bars.right, bars.bottom)
            insets
        }

        val title = findViewById<TextView>(R.id.document_title)
        ViewCompat.setAccessibilityHeading(title, true)
        val status = findViewById<TextView>(R.id.status)
        val button = findViewById<Button>(R.id.open_file)
        val documentView = findViewById<RecyclerView>(R.id.document)
        val adapter = OrgAdapter()
        documentView.layoutManager = LinearLayoutManager(this)
        documentView.adapter = adapter
        button.setOnClickListener {
            // Providers do not consistently assign a MIME type to .org files.
            openDocument.launch(arrayOf("*/*"))
        }

        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                model.state.collect { state ->
                    button.isEnabled = !state.loading
                    title.text = state.document?.let { it.name.ifBlank { getString(R.string.untitled_document) } }
                        ?: getString(R.string.app_name)
                    val message = when {
                        state.loading -> R.string.loading_message
                        state.failed -> R.string.error_message
                        state.document == null -> R.string.initial_message
                        state.document.blocks.isEmpty() -> R.string.empty_message
                        else -> null
                    }
                    status.visibility = if (message == null) View.GONE else View.VISIBLE
                    if (message != null) status.setText(message)
                    adapter.show(state.document?.blocks.orEmpty())
                }
            }
        }
    }
}
