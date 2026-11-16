plugins {
    // Must match the engine's Kotlin: its classes carry metadata from 2.4.21, and an older
// compiler fails on them.
    kotlin("jvm") version "2.4.21" apply false
}
