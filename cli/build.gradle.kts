plugins {
    kotlin("jvm")
    application
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    // Resolved from the included build, pinned by the submodule commit. Never from a registry.
    implementation("app.morphe:morphe-patcher")
}

application {
    mainClass.set("app.maxyoutube.cli.MainKt")
}

// One jar that runs anywhere, so the build can happen where there is CPU and the run where the
// input APK is, without the APK ever being uploaded.
tasks.register<Jar>("fatJar") {
    group = "build"
    archiveBaseName.set("max-youtube-cli")
    archiveClassifier.set("all")
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
    manifest { attributes["Main-Class"] = "app.maxyoutube.cli.MainKt" }
    from(sourceSets.main.get().output)
    // Resolved lazily: resolving the runtime classpath during configuration reaches into the
    // included engine build, which Gradle refuses at that point.
    from({ configurations.runtimeClasspath.get().map { if (it.isDirectory) it else zipTree(it) } })
    exclude("META-INF/*.SF", "META-INF/*.DSA", "META-INF/*.RSA", "META-INF/versions/9/module-info.class")
}
