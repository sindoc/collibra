(ns smtpagent.parser
  "Singine parser layer — reads EDN meta-config and validates
   inbound JSON command maps from the HTTP/TCP relay.

   Grammar handled:
     config  := EDN map conforming to meta/config.edn schema
     command := JSON object  { cmd, from?, to, subject, body, [template?] }

   The parser returns normalised Clojure maps; the interpreter (core.clj)
   drives execution from those maps."
  (:require [clojure.edn        :as edn]
            [clojure.data.json  :as json]
            [clojure.string     :as str]
            [clojure.tools.logging :as log]))

;; ── EDN meta-config parser ────────────────────────────────────────────────────

(defn load-meta-config
  "Read and parse meta/config.edn from `path`.
   Returns the :singine sub-map."
  [path]
  (try
    (let [raw  (slurp path)
          data (edn/read-string raw)]
      (log/info "Meta-config loaded from" path)
      (:singine data))
    (catch Exception e
      (log/error "Failed to load meta-config:" (.getMessage e))
      nil)))

;; ── Command validator ─────────────────────────────────────────────────────────

(def ^:private required-send-keys [:to :subject :body])

(defn- validate-send [cmd]
  (let [missing (filter #(str/blank? (get cmd %)) required-send-keys)]
    (if (seq missing)
      {:valid? false :error (str "Missing fields: " (str/join ", " (map name missing)))}
      {:valid? true})))

(defn- validate-ping [_cmd] {:valid? true})

(defn- validate-status [_cmd] {:valid? true})

(def ^:private validators
  {:send   validate-send
   :ping   validate-ping
   :status validate-status})

;; ── JSON command parser ───────────────────────────────────────────────────────

(defn parse-command
  "Parse a raw JSON string into a validated command map.
   Returns {:valid? true/false :cmd <keyword> :data <map> [:error <str>]}"
  [raw-json allowed-commands]
  (try
    (let [m    (json/read-str raw-json :key-fn keyword)
          cmd  (keyword (or (:cmd m) "unknown"))]
      (if-not (contains? allowed-commands cmd)
        {:valid? false :error (str "Unknown command: " (name cmd))}
        (let [validation ((get validators cmd validate-ping) m)]
          (merge validation {:cmd cmd :data m}))))
    (catch Exception e
      (log/warn "parse-command error:" (.getMessage e))
      {:valid? false :error (str "JSON parse error: " (.getMessage e))})))

;; ── Template expander ─────────────────────────────────────────────────────────

(defn expand-template
  "Perform {{key}} substitution in `template-str` using `values` map."
  [template-str values]
  (reduce (fn [s [k v]]
            (str/replace s (str "{{" (name k) "}}") (str v)))
          template-str
          values))
