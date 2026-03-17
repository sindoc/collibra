(defproject singine-persistence "1.0.0"
  :description "Singine persistence — categories, similarity, reification (JVM)"
  :url         "https://github.com/sindoc/collibra"
  :license     {:name "Proprietary"}

  :dependencies
  [[org.clojure/clojure      "1.11.1"]
   ;; SQLite JDBC
   [org.xerial/sqlite-jdbc   "3.45.3.0"]
   ;; Clojure JDBC
   [com.github.seancorfield/next.jdbc "1.3.939"]
   ;; EDN / data
   [org.clojure/data.json    "2.4.0"]
   ;; Spec for validated algorithms
   [org.clojure/spec.alpha   "0.3.218"]
   ;; Logging
   [org.clojure/tools.logging "1.3.0"]
   [ch.qos.logback/logback-classic "1.4.14"]
   ;; CLI
   [org.clojure/tools.cli    "1.1.230"]]

  :main ^:skip-aot singine.persistence.core
  :target-path "target/%s"
  :source-paths ["src"]
  :resource-paths ["resources"]

  :profiles
  {:uberjar {:aot :all}})
