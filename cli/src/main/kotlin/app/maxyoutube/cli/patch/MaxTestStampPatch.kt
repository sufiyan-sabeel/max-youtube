package app.maxyoutube.cli.patch

import app.morphe.patcher.patch.resourcePatch

/**
 * The one customisation of the prototype: stamp the build into the manifest's versionName.
 *
 * Chosen because it is verifiable (the output's manifest is re-read and asserted), reversible (the
 * input APK is opened read-only and the output is a new file) and harmless (no dex edit, no resource
 * table edit, no behaviour change).
 *
 * @param stampedVersionName The versionName the patched manifest carries.
 */
fun maxTestStampPatch(stampedVersionName: String) = resourcePatch(
    name = "MAX test build stamp",
    description = "Marks the APK as a MAX YouTube TEST BUILD in its manifest. Cosmetic and reversible.",
) {
    execute {
        // Document is a DOM Document that writes itself back to the APK when closed.
        document("AndroidManifest.xml").use { manifest ->
            manifest.documentElement.setAttributeNS(
                "http://schemas.android.com/apk/res/android",
                "android:versionName",
                stampedVersionName,
            )
        }
    }
}
