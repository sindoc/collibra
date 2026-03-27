#!/usr/bin/env groovy
// JProfilerAttach.groovy — JProfiler attach and control for Groovy/JVM processes.
//
// Grammar reference: docs/xml/chip-queries.xml jprofiler-targets id="groovy-process"
// Companion:         uniWork/persistence/clojure/src/persistence/jprofiler.clj
// Launched from:     Go lang=XML.g() chip_queries.go jprofiler target discovery
//
// Usage:
//   groovy JProfilerAttach.groovy [status|start|stop [<out-dir>]]
//
// JVM agent flag required at process startup:
//   java -agentpath:/opt/jprofiler/bin/linux-x64/libjprofilerti.so=port=8849,nowait=y ...

import groovy.json.JsonOutput
import groovy.transform.CompileStatic

@CompileStatic
class JProfilerAttach {

    static final int    JPROFILER_PORT = 8849
    static final String CONFIG_ID      = "chip.profiler.groovy"
    static final String RUNTIME_LABEL  = "groovy"
    static final String DEFAULT_OUTDIR = "/tmp/jprofiler-groovy"

    // ── status ───────────────────────────────────────────────────────────────

    static Map<String, Object> status() {
        Map<String, Object> result = [
            runtime   : RUNTIME_LABEL,
            config_id : CONFIG_ID,
            port      : JPROFILER_PORT,
            timestamp : new Date().toInstant().toString(),
        ]
        try {
            Class<?> ctrl = Class.forName("com.jprofiler.api.agent.Controller")
            boolean active = (Boolean) ctrl.getMethod("isAgentActive").invoke(null)
            result.profiler_active = active
            result.ok = true
        } catch (ClassNotFoundException ignored) {
            result.profiler_active = false
            result.ok = false
            result.note = "JProfiler agent not on classpath — add -agentpath to JVM args"
        } catch (Throwable t) {
            result.profiler_active = false
            result.ok = false
            result.error = t.message
        }
        return result
    }

    // ── start CPU recording ──────────────────────────────────────────────────

    static Map<String, Object> startCpuRecording(String sessionLabel = "chip-query-session") {
        try {
            Class<?> ctrl = Class.forName("com.jprofiler.api.agent.Controller")
            ctrl.getMethod("startCPURecording", boolean).invoke(null, true)
            return [ok: true, session: sessionLabel, runtime: RUNTIME_LABEL]
        } catch (ClassNotFoundException ignored) {
            return [ok: false, error: "JProfiler agent not on classpath", runtime: RUNTIME_LABEL]
        } catch (Throwable t) {
            return [ok: false, error: t.message, runtime: RUNTIME_LABEL]
        }
    }

    // ── stop and save snapshot ───────────────────────────────────────────────

    static Map<String, Object> stopAndSnapshot(String outDir = DEFAULT_OUTDIR) {
        try {
            new File(outDir).mkdirs()
            Class<?> ctrl = Class.forName("com.jprofiler.api.agent.Controller")
            ctrl.getMethod("stopCPURecording").invoke(null)
            String snapshotFile = "${outDir}/groovy-${System.currentTimeMillis()}.jps"
            ctrl.getMethod("saveSnapshot", String).invoke(null, snapshotFile)
            return [ok: true, snapshot: snapshotFile, runtime: RUNTIME_LABEL]
        } catch (ClassNotFoundException ignored) {
            return [ok: false, error: "JProfiler agent not on classpath", runtime: RUNTIME_LABEL]
        } catch (Throwable t) {
            return [ok: false, error: t.message, runtime: RUNTIME_LABEL]
        }
    }

    // ── entry point ──────────────────────────────────────────────────────────

    static void main(String[] args) {
        String cmd = args.length > 0 ? args[0] : "status"
        Map<String, Object> result
        switch (cmd) {
            case "start":
                result = startCpuRecording(args.length > 1 ? args[1] : "chip-query-session")
                break
            case "stop":
                result = stopAndSnapshot(args.length > 1 ? args[1] : DEFAULT_OUTDIR)
                break
            default:
                result = status()
        }
        println JsonOutput.toJson(result)
    }
}
