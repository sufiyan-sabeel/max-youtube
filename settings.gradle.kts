rootProject.name = "max-youtube"

// The runner and the engine resolve their dependencies from these. Google's repository is needed for
// com.android.tools.build:apksig and apkzlib, which the engine signs with.
dependencyResolutionManagement {
    repositories {
        mavenCentral()
        google()
    }
}

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
