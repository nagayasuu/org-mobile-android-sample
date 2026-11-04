plugins {
    id("com.android.application")
}

android {
    namespace = "dev.orgmobile.reader"
    compileSdk = 37
    buildToolsVersion = "37.0.0"

    defaultConfig {
        applicationId = "dev.orgmobile.reader"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        testInstrumentationRunnerArguments["disableAnalytics"] = "true"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    testOptions {
        unitTests.isIncludeAndroidResources = true
        animationsDisabled = true
        managedDevices {
            localDevices {
                create("pixel2Api37") {
                    device = "Pixel 2"
                    apiLevel = 37
                    systemImageSource = "google"
                    testedAbi = "x86_64"
                    pageAlignment = com.android.build.api.dsl.ManagedVirtualDevice.PageAlignment.FORCE_4KB_PAGES
                }
            }
        }
    }
    // Package the public fixture only in the instrumentation APK.
    sourceSets.getByName("androidTest").assets.directories.add(rootProject.file("examples").path)
    lint {
        warningsAsErrors = true
        abortOnError = true
    }
}

apply(from = rootProject.file("gradle/coverage.gradle"))

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        allWarningsAsErrors.set(true)
    }
}

androidComponents {
    beforeVariants(selector().all()) { variant ->
        variant.hostTests[com.android.build.api.variant.HostTestBuilder.UNIT_TEST_TYPE]?.enable = true
    }
}

tasks.withType<Test>().configureEach {
    // Pass the replay seed to the forked JVM and invalidate cached test results.
    providers.gradleProperty("propertyTestSeed").orNull?.let {
        systemProperty("orgmobile.property.seed", it.toLong().toString())
    }
    systemProperty("kotest.proptest.seed.write-failed", "false")
}

dependencies {
    implementation("androidx.activity:activity-ktx:1.11.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-savedstate:2.9.4")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.4")
    implementation("androidx.recyclerview:recyclerview:1.4.0")

    testImplementation("junit:junit:4.13.2")
    testImplementation("io.kotest:kotest-property:6.2.6")
    testImplementation("com.tngtech.archunit:archunit:1.5.1")
    testImplementation("org.robolectric:robolectric:4.16")
    testImplementation("androidx.test:core:1.7.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")

    androidTestImplementation("androidx.test:core:1.7.0")
    androidTestImplementation("androidx.test:runner:1.7.0")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    androidTestImplementation("androidx.test.espresso:espresso-contrib:3.7.0")
    androidTestImplementation("androidx.test.uiautomator:uiautomator:2.4.0")
}
