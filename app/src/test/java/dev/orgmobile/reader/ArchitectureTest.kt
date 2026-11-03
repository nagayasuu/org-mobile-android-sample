package dev.orgmobile.reader

import com.tngtech.archunit.base.DescribedPredicate
import com.tngtech.archunit.core.domain.JavaClass
import com.tngtech.archunit.core.importer.ClassFileImporter
import com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses
import org.junit.Assert.assertTrue
import org.junit.Test

class ArchitectureTest {
    @Test
    fun parserAndBlocksDoNotDependOnAndroidOrFileAccess() {
        noClasses().that(family("OrgParser", "OrgBlock"))
            .should().dependOnClassesThat(
                android.or(applicationOutside("OrgParser", "OrgBlock"))
                    .or(inPackages("java.io", "java.nio.file", "java.net")),
            )
            .because("org parsing must stay independent of Android, UI and file access")
            .check(productionClasses)
    }

    @Test
    fun decoderOnlyUsesPlatformIndependentParsingAndStreamDecoding() {
        noClasses().that(family("DocumentDecoder"))
            .should().dependOnClassesThat(
                android.or(applicationOutside("DocumentDecoder", "OrgParser", "OrgBlock")),
            )
            .because("decoding receives a stream and must not access Android or providers")
            .check(productionClasses)
    }

    @Test
    fun viewModelDoesNotDependOnScreensOrConcreteDocumentSource() {
        noClasses().that(family("ReaderViewModel"))
            .should().dependOnClassesThat(
                family("MainActivity", "OrgAdapter", "ContentDocumentSource")
                    .or(inPackages(
                        "android.app", "android.view", "android.widget", "android.webkit",
                        "androidx.activity", "androidx.fragment", "androidx.recyclerview",
                    )),
            )
            .because("the ViewModel reads through DocumentSource and leaves rendering to UI")
            .check(productionClasses)
    }

    @Test
    fun importsEveryRuleRootAndItsKnownNestedClasses() {
        val importedNames = productionClasses.map { it.name }.toSet()
        listOf(
            "OrgParser", "OrgParser\$Parser", "OrgBlock", "OrgBlock\$Heading",
            "OrgBlock\$Paragraph", "OrgBlock\$ListItem", "DocumentDecoder",
            "ReaderViewModel", "ReaderViewModel\$Companion",
        ).forEach { name ->
            assertTrue("Missing production class: $name", "$PACKAGE.$name" in importedNames)
        }
        assertTrue("Test classes must not be imported", javaClass.name !in importedNames)
    }

    companion object {
        private const val PACKAGE = "dev.orgmobile.reader"

        // AGP uses debugUnitTest/releaseUnitTest paths, unlike the usual JVM test paths.
        // Exclude the actual test output location rather than guessing its directory name.
        private val testOutput = requireNotNull(ArchitectureTest::class.java.protectionDomain)
            .codeSource.location.toURI().toString()
        private val productionClasses = ClassFileImporter()
            .withImportOption { !it.asURI().toString().startsWith(testOutput) }
            .importPackages(PACKAGE)

        private fun family(vararg names: String): DescribedPredicate<JavaClass> =
            object : DescribedPredicate<JavaClass>("class families ${names.toList()}") {
                override fun test(input: JavaClass): Boolean = names.any { name ->
                    input.name == "$PACKAGE.$name" || input.name.startsWith("$PACKAGE.$name\$")
                }
            }

        private fun inPackages(vararg names: String): DescribedPredicate<JavaClass> =
            object : DescribedPredicate<JavaClass>("packages ${names.toList()}") {
                override fun test(input: JavaClass): Boolean = names.any { name ->
                    input.packageName == name || input.packageName.startsWith("$name.")
                }
            }

        private val android = inPackages("android", "androidx", "com.android")

        private fun applicationOutside(vararg allowed: String): DescribedPredicate<JavaClass> =
            inPackages(PACKAGE).and(DescribedPredicate.not(family(*allowed)))
    }
}
