rootProject.name = "max-youtube"

pluginManagement {
    repositories {
        mavenCentral()
        gradlePluginPortal()
    }
}

// The engine is used from source at a pinned commit, not from the Morphe registry: that registry
// answers 401 without a token, and substituting the module keeps the pin explicit and auditable.
includeBuild("vendor/max-patcher/engine") {
    dependencySubstitution {
        substitute(module("app.morphe:morphe-patcher")).using(project(":"))
    }
}

include(":cli")
