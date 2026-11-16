package app.maxyoutube.cli

import app.morphe.patcher.InternalApi
import app.morphe.patcher.Patcher
import app.morphe.patcher.PatcherConfig
import app.morphe.patcher.apk.ApkSigner
import app.morphe.patcher.apk.ApkUtils.applyTo
import app.maxyoutube.cli.patch.maxAppLabelPatch
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest

/**
 * The standalone MAX YouTube runner.
 *
 * Takes an original YouTube APK, applies one verified customisation through the pinned MAX Engine,
 * signs the result with a test key, and writes a JSON report beside it.
 *
 * The input APK is opened read-only and is never modified: the patched output is a new file.
 */
private class Args(argv: Array<String>) {
    private val values = HashMap<String, String>()

    init {
        var i = 0
        while (i < argv.size) {
            val key = argv[i]
            require(key.startsWith("--")) { "unexpected argument: $key" }
            require(i + 1 < argv.size) { "missing value for $key" }
            values[key.removePrefix("--")] = argv[i + 1]
            i += 2
        }
    }

    fun required(name: String): String =
        values[name] ?: throw IllegalArgumentException("--$name is required")

    fun optional(name: String): String? = values[name]
}

private fun sha256(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().use { input ->
        val buffer = ByteArray(1 shl 20)
        while (true) {
            val read = input.read(buffer)
            if (read <= 0) break
            digest.update(buffer, 0, read)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}

private fun jsonEscape(value: String) =
    value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")

@OptIn(InternalApi::class)
fun main(argv: Array<String>) {
    val args = Args(argv)
    val inputApk = File(args.required("apk"))
    val outDir = File(args.required("out")).apply { mkdirs() }
    val keystore = File(args.required("keystore"))
    val alias = args.required("alias")
    val passwordEnv = args.required("password-env")
    val stampedVersionName = args.required("stamp")
    val label = args.required("label")
    val outputName = args.required("name")

    val password = System.getenv(passwordEnv)
        ?: throw IllegalStateException("$passwordEnv is not set; the password is never passed on the command line")

    require(inputApk.isFile) { "no such APK: $inputApk" }
    require(keystore.isFile) { "no such keystore: $keystore" }

    val inputSha = sha256(inputApk)
    println("input   $inputApk")
    println("sha256  $inputSha")

    val workDir = Files.createTempDirectory("max-youtube-work").toFile()
    val unsigned = File(outDir, "$outputName.unsigned.apk")
    val signed = File(outDir, outputName)

    val warnings = mutableListOf<String>()

    val patcher = Patcher(
        PatcherConfig(
            apkFile = inputApk,
            temporaryFilesPath = workDir,
        )
    )

    val results = patcher.use {
        it += setOf(maxAppLabelPatch(label, stampedVersionName))
        val collected = runBlocking { it().toList() }
        collected.forEach { result ->
            val exception = result.exception
            println("patch   ${result.patch.name}: ${if (exception == null) "ok" else "FAILED: ${exception.message}"}")
            if (exception != null) throw exception
        }
        it.get()
    }

    results.applyTo(unsigned)
    println("patched $unsigned")

    val keyStore = ApkSigner.readKeyStore(keystore.inputStream(), password)
    val pair = ApkSigner.readPrivateKeyCertificatePair(keyStore, alias, password)
    val signer = ApkSigner.newApkSigner("max-youtube-test", pair)
    signer.signApk(unsigned, signed, minSdkVersion = 32)
    unsigned.delete()
    println("signed  $signed")

    val outputSha = sha256(signed)
    val fingerprint = pair.certificate.encoded.let {
        MessageDigest.getInstance("SHA-256").digest(it).joinToString("") { b -> "%02x".format(b) }
    }

    if (stampedVersionName.contains("TEST", ignoreCase = true)) {
        // nothing to warn about: the stamp is the label
    } else {
        warnings.add("the stamped versionName does not mark the build as a TEST BUILD")
    }

    val report = buildString {
        appendLine("{")
        appendLine("  \"tool\": \"max-youtube-cli\",")
        appendLine("  \"input\": {")
        appendLine("    \"name\": \"${jsonEscape(inputApk.name)}\",")
        appendLine("    \"sha256\": \"$inputSha\"")
        appendLine("  },")
        appendLine("  \"output\": {")
        appendLine("    \"name\": \"${jsonEscape(signed.name)}\",")
        appendLine("    \"sizeBytes\": ${signed.length()},")
        appendLine("    \"sha256\": \"$outputSha\"")
        appendLine("  },")
        appendLine("  \"patch\": \"${jsonEscape("MAX app name")}\",")
        appendLine("  \"appLabel\": \"${jsonEscape(label)}\",")
        appendLine("  \"stampedVersionName\": \"${jsonEscape(stampedVersionName)}\",")
        appendLine("  \"signing\": {")
        appendLine("    \"alias\": \"${jsonEscape(alias)}\",")
        appendLine("    \"certificateSha256\": \"$fingerprint\"")
        appendLine("  },")
        appendLine("  \"warnings\": [${warnings.joinToString(", ") { "\"${jsonEscape(it)}\"" }}]")
        appendLine("}")
    }

    val reportFile = File(outDir, "build-report.json")
    reportFile.writeText(report)
    println()
    println(report)
    println("report  $reportFile")
}
