(ns smtpagent.core
  "Singine smtpAgent — interpreter entry point.
   Exposes an HTTP server on port 8026 (loopback) that:
     POST /send   — parse + validate + send email
     GET  /ping   — liveness probe
     GET  /status — SMTP config status (no credentials leaked)
   The C TCP acceptor (port 8025) relays inbound requests here."
  (:require [compojure.core       :refer [defroutes GET POST]]
            [compojure.route      :refer [not-found]]
            [ring.adapter.jetty   :refer [run-jetty]]
            [ring.middleware.json :refer [wrap-json-body wrap-json-response]]
            [ring.util.response   :refer [response status]]
            [clojure.data.json    :as json]
            [clojure.tools.logging :as log]
            [smtpagent.parser     :as parser]
            [smtpagent.smtp       :as smtp])
  (:gen-class))

;; ── Load meta-config at startup ───────────────────────────────────────────────

(def ^:private META-CONFIG-PATH
  (or (System/getenv "SINGINE_META_CONFIG")
      "../meta/config.edn"))

(defonce ^:private cfg (atom nil))

(defn- load-config! []
  (when-let [c (parser/load-meta-config META-CONFIG-PATH)]
    (reset! cfg c)
    (log/info "Singine meta-config active:" (select-keys c [:engine :version]))))

;; ── Interpreter ───────────────────────────────────────────────────────────────

(defn- interpret
  "Core interpreter: dispatch parsed command to the appropriate handler."
  [parsed]
  (let [data             (:data parsed)
        smtp-cfg         (:smtp @cfg {})
        allowed-commands (get-in @cfg [:interpreter :allowed-commands]
                                 #{:send :ping :status})]
    (case (:cmd parsed)
      :send   (smtp/send-email smtp-cfg data)
      :ping   {:ok true :pong true}
      :status {:ok true :smtp (smtp/smtp-status smtp-cfg)
                          :version (:version @cfg "unknown")}
      :reload-config (do (load-config!) {:ok true :reloaded true})
      {:ok false :error "Unhandled command"})))

;; ── HTTP routes ───────────────────────────────────────────────────────────────

(defroutes app-routes
  ;; Liveness probe
  (GET "/ping" []
    (response {:ok true :service "smtpagent"}))

  ;; Status — safe subset of config, no credentials
  (GET "/status" []
    (if @cfg
      (response {:ok    true
                 :smtp  (smtp/smtp-status (:smtp @cfg {}))
                 :engine (:engine @cfg)
                 :version (:version @cfg)})
      (-> (response {:ok false :error "Config not loaded"}) (status 503))))

  ;; Main send endpoint — called by Python web server or C relay
  (POST "/send" req
    (let [allowed (get-in @cfg [:interpreter :allowed-commands] #{:send :ping :status})
          body    (if (string? (:body req))
                    (:body req)
                    (json/write-str (:body req)))
          parsed  (parser/parse-command
                    (if (map? (:body req))
                      ;; already parsed by wrap-json-body
                      (json/write-str (assoc (:body req) :cmd "send"))
                      body)
                    allowed)]
      (if (:valid? parsed)
        (let [result (interpret parsed)]
          (if (:ok result)
            (response result)
            (-> (response result) (status 500))))
        (-> (response {:ok false :error (:error parsed)}) (status 400)))))

  (not-found {:ok false :error "Not found"}))

;; ── Ring middleware stack ─────────────────────────────────────────────────────

(def app
  (-> app-routes
      (wrap-json-body {:keywords? true :bigdecimals? true})
      wrap-json-response))

;; ── Main ──────────────────────────────────────────────────────────────────────

(defn -main [& _args]
  (load-config!)
  (let [port (Integer/parseInt (or (System/getenv "SMTP_SERVICE_PORT") "8026"))]
    (log/info "Singine smtpAgent starting on port" port)
    (run-jetty app {:port  port
                    :host  "127.0.0.1"   ;; loopback only — C relay is the public face
                    :join? true})))
