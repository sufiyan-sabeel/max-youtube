package app.maxyoutube.cli.patch

import app.morphe.patcher.patch.resourcePatch

/**
 * User-visible customisation: the app's name, as every surface shows it.
 *
 * The launcher, the recents card, the share sheet and Settings all read `android:label` from the
 * application element of the manifest, so setting it there renames the app everywhere it appears. The
 * attribute is confirmed present in the inspected APK.
 *
 * The change is a string in the manifest only: no dex edit, no resource-table edit beyond the manifest
 * itself, no behaviour change, and the input APK is opened read-only.
 *
 * @param label The name to show.
 * @param stampedVersionName A versionName that marks the build as a test build, or null to leave it.
 */
fun maxAppLabelPatch(label: String, stampedVersionName: String? = null) = resourcePatch(
    name = "MAX app name",
    description = "Renames the app to \"$label\" everywhere Android shows it. Reversible.",
) {
    execute {
        document("AndroidManifest.xml").use { manifest ->
            val androidNamespace = "http://schemas.android.com/apk/res/android"
            val application = manifest.getElementsByTagName("application").item(0)
                ?: error("the manifest has no <application> element")

            (application as org.w3c.dom.Element).setAttributeNS(androidNamespace, "android:label", label)

            if (stampedVersionName != null) {
                manifest.documentElement.setAttributeNS(
                    androidNamespace,
                    "android:versionName",
                    stampedVersionName,
                )
            }
        }
    }
}
