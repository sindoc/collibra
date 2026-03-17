(defproject smtpagent "1.0.0"
  :description "Singine smtpAgent — JVM SMTP service with EDN parser and interpreter"
  :url         "https://github.com/sindoc/collibra"
  :license     {:name "Proprietary"}

  :dependencies
  [[org.clojure/clojure       "1.11.1"]
   ;; HTTP server (Ring stack)
   [ring/ring-core            "1.11.0"]
   [ring/ring-jetty-adapter   "1.11.0"]
   [compojure                 "1.7.1"]
   [ring/ring-json            "0.5.1"]
   ;; SMTP via JavaMail (postal wraps javax.mail)
   [com.draines/postal        "2.0.5"]
   ;; EDN/data utilities
   [org.clojure/data.json     "2.4.0"]
   ;; Logging
   [org.clojure/tools.logging "1.3.0"]
   [ch.qos.logback/logback-classic "1.4.14"]]

  :main ^:skip-aot smtpagent.core
  :target-path "target/%s"

  :profiles
  {:uberjar {:aot :all
             :jvm-opts ["-Dclojure.compiler.direct-linking=true"]}
   :dev     {:dependencies [[ring/ring-mock "0.4.0"]]}}

  :source-paths ["src"]
  :resource-paths ["resources"])
