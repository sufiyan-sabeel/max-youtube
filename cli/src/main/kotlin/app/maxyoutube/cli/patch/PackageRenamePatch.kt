package app.maxyoutube.cli.patch

import app.morphe.patcher.patch.resourcePatch
import org.w3c.dom.Element

private const val ANDROID_NS = "http://schemas.android.com/apk/res/android"

/**
 * Gives the build its own application id so it can live beside the official app.
 *
 * What changes, and why:
 *
 *  - `manifest@package` becomes the new id, which is what Android uses to tell two apps apart;
 *  - every component name written relative to the old package (`.SomeActivity`) becomes absolute
 *    (`com.google.android.youtube.SomeActivity`), because a relative name would otherwise resolve against
 *    the new id and find no such class — the app would start and immediately crash;
 *  - declared permissions and provider authorities namespaced under the old package move to the new one,
 *    so the two apps collide on neither.
 *
 * What deliberately does not change: component class names themselves, Java/Kotlin package names, dex
 * contents, deep-link schemes and hosts, and references to other apps. Renaming a class would break the
 * app, and the application id is not the Java package.
 *
 * @param newPackage The application id to apply.
 */
fun packageRenamePatch(newPackage: String) = resourcePatch(
    name = "MAX package identity",
    description = "Sets the application id to $newPackage so it installs beside the official app.",
) {
    execute {
        document("AndroidManifest.xml").use { manifest ->
            val root = manifest.documentElement
            val original = root.getAttribute("package")
            require(original.isNotEmpty()) { "the manifest declares no package" }

            root.setAttribute("package", newPackage)

            val elements = manifest.getElementsByTagName("*")
            for (i in 0 until elements.length) {
                val element = elements.item(i) as? Element ?: continue

                // Relative component names must stay resolvable to the classes that exist.
                val name = element.getAttributeNS(ANDROID_NS, "name")
                if (name.startsWith(".")) {
                    element.setAttributeNS(ANDROID_NS, "android:name", original + name)
                } else if (name.startsWith("$original.") && element.tagName in SELF_NAMESPACED) {
                    element.setAttributeNS(ANDROID_NS, "android:name", newPackage + name.removePrefix(original))
                }

                // Authorities and permissions are identity, not code: they move with the app.
                val authorities = element.getAttributeNS(ANDROID_NS, "authorities")
                if (authorities.isNotEmpty() && authorities.contains(original)) {
                    element.setAttributeNS(
                        ANDROID_NS,
                        "android:authorities",
                        authorities.replace(original, newPackage),
                    )
                }
            }
        }
    }
}

/** Elements whose own name is an identity the app declares, rather than a class it loads. */
private val SELF_NAMESPACED = setOf("permission", "uses-permission", "permission-group", "uses-permission-sdk-23")
