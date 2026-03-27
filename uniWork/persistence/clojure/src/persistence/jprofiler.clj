(ns persistence.jprofiler
  "JProfiler attach and control for the Clojure JVM persistence process.

   Grammar reference: docs/xml/chip-queries.xml jprofiler-targets id=\"clojure-process\"
   Companion:         uniWork/persistence/groovy/JProfilerAttach.groovy
   Launched from:     Go lang=XML.g() chip_queries.go jprofiler target discovery

   JVM agent flag required at process startup:
     java -agentpath:/opt/jprofiler/bin/linux-x64/libjprofilerti.so=port=8849,nowait=y ...

   Usage:
     lein run -m persistence.jprofiler [status|start|stop [<out-dir>]]"
  (:require [clojure.data.json :as json])
  (:gen-class))

(def ^:const JPROFILER-PORT 8849)
(def ^:const CONFIG-ID      "chip.profiler.clojure")
(def ^:const RUNTIME-LABEL  "clojure")
(def ^:const DEFAULT-OUTDIR "/tmp/jprofiler-clojure")

;; ── controller reflection (soft dependency on jprofiler agent) ─────────────

(defn- ctrl []
  (try
    (Class/forName "com.jprofiler.api.agent.Controller")
    (catch ClassNotFoundException _ nil)))

(defn- ctrl-invoke [^String method-name & typed-args]
  (when-let [cls (ctrl)]
    (let [arg-types  (mapv first  typed-args)
          arg-values (mapv second typed-args)
          m          (.getMethod cls method-name (into-array Class arg-types))]
      (.invoke m nil (object-array arg-values)))))

;; ── status ────────────────────────────────────────────────────────────────────

(defn status []
  (let [base {:runtime    RUNTIME-LABEL
              :config_id  CONFIG-ID
              :port       JPROFILER-PORT
              :timestamp  (str (java.time.Instant/now))}]
    (if-not (ctrl)
      (assoc base
             :ok false
             :profiler_active false
             :note "JProfiler agent not on classpath — add -agentpath to JVM args")
      (try
        (let [active (ctrl-invoke "isAgentActive")]
          (assoc base :ok true :profiler_active (boolean active)))
        (catch Throwable t
          (assoc base :ok false :profiler_active false :error (.getMessage t)))))))

;; ── start CPU recording ───────────────────────────────────────────────────────

(defn start-cpu-recording
  ([] (start-cpu-recording "chip-query-session"))
  ([session-label]
   (if-not (ctrl)
     {:ok false :error "JProfiler agent not on classpath" :runtime RUNTIME-LABEL}
     (try
       (ctrl-invoke "startCPURecording" [Boolean/TYPE true])
       {:ok true :session session-label :runtime RUNTIME-LABEL}
       (catch Throwable t
         {:ok false :error (.getMessage t) :runtime RUNTIME-LABEL})))))

;; ── stop and save snapshot ────────────────────────────────────────────────────

(defn stop-and-snapshot
  ([] (stop-and-snapshot DEFAULT-OUTDIR))
  ([out-dir]
   (if-not (ctrl)
     {:ok false :error "JProfiler agent not on classpath" :runtime RUNTIME-LABEL}
     (try
       (.mkdirs (java.io.File. out-dir))
       (ctrl-invoke "stopCPURecording")
       (let [snapshot (format "%s/clojure-%d.jps" out-dir (System/currentTimeMillis))]
         (ctrl-invoke "saveSnapshot" [String snapshot])
         {:ok true :snapshot snapshot :runtime RUNTIME-LABEL})
       (catch Throwable t
         {:ok false :error (.getMessage t) :runtime RUNTIME-LABEL})))))

;; ── entry point ───────────────────────────────────────────────────────────────

(defn -main [& args]
  (let [cmd    (or (first args) "status")
        result (case cmd
                 "start" (start-cpu-recording (or (second args) "chip-query-session"))
                 "stop"  (stop-and-snapshot   (or (second args) DEFAULT-OUTDIR))
                 (status))]
    (println (json/write-str result))))
