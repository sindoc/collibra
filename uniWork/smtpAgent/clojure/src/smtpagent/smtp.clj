(ns smtpagent.smtp
  "SMTP send layer — wraps com.draines/postal (JavaMail).
   All credentials come from environment variables; never from config files."
  (:require [postal.core        :as postal]
            [clojure.tools.logging :as log]))

;; ── SMTP connection map ───────────────────────────────────────────────────────

(defn- build-smtp-conn [cfg]
  {:host (:host cfg "smtp.gmail.com")
   :port (:port cfg 587)
   :tls  (:tls  cfg true)
   :user (System/getenv "SMTP_USER")
   :pass (System/getenv "SMTP_PASS")})

;; ── Send ─────────────────────────────────────────────────────────────────────

(defn send-email
  "Send an email using the SMTP config `cfg` and command data `data`.
   Returns {:ok true} or {:ok false :error <str>}."
  [cfg data]
  (let [smtp-conn (build-smtp-conn cfg)
        from-addr (or (:from data) (System/getenv "SMTP_USER") "noreply@localhost")
        msg       {:from    from-addr
                   :to      [(:to data)]
                   :subject (:subject data "(no subject)")
                   :body    (:body data "")}]
    (if (or (nil? (:user smtp-conn)) (nil? (:pass smtp-conn)))
      (do
        (log/error "SMTP_USER or SMTP_PASS env vars not set")
        {:ok false :error "SMTP credentials not configured (set SMTP_USER / SMTP_PASS)"})
      (try
        (log/info "Sending email to" (:to data))
        (let [result (postal/send-message smtp-conn msg)]
          (if (= :SUCCESS (:error result))
            (do (log/info "Email sent OK") {:ok true})
            (do (log/warn "SMTP error:" result)
                {:ok false :error (str result)})))
        (catch Exception e
          (log/error "send-email exception:" (.getMessage e))
          {:ok false :error (.getMessage e)})))))

;; ── Status probe ──────────────────────────────────────────────────────────────

(defn smtp-status [cfg]
  {:host      (:host cfg "smtp.gmail.com")
   :port      (:port cfg 587)
   :tls       (:tls  cfg true)
   :user-set? (some? (System/getenv "SMTP_USER"))
   :pass-set? (some? (System/getenv "SMTP_PASS"))})
